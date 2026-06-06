"""Happy Path Pipeline — 线性执行章节解析→角色→场景→剧本→校验"""

import json
from state.models import SessionState, PipelineStatus
from state.sqlite_store import SQLiteStateStore
from agents.chapter_parser import ChapterParser
from agents.character_agent import CharacterAgent
from agents.scene_agent import SceneAgent
from agents.script_agent import ScriptAgent
from agents.validator import Validator
from llm.factory import AdapterFactory


class Pipeline:
    AGENT_ORDER = ["chapter_parser", "character_agent", "scene_agent", "script_agent", "validator"]

    def __init__(self, state_store: SQLiteStateStore | None = None):
        self.state_store = state_store or SQLiteStateStore()
        self.parser = ChapterParser()
        self.validator = Validator()

    async def execute(self, state: SessionState) -> SessionState:
        llm_adapter = AdapterFactory.from_env()

        try:
            # Step 1: 章节解析（规则引擎）
            state.status = PipelineStatus.PARSING
            state.pipeline_state.current_agent = "chapter_parser"
            await self._persist(state)

            if state.artifacts.chapters and state.artifacts.chapters[0].get("text"):
                chapters = self.parser.parse(state.artifacts.chapters[0]["text"])
                state.artifacts.chapters = chapters
            state.pipeline_state.checkpoint_stack.append("parser_done")

            # Step 2: 角色识别
            state.status = PipelineStatus.CHAR_EXTRACTING
            state.pipeline_state.current_agent = "character_agent"
            state.pipeline_state.progress = 0.2
            await self._persist(state)

            char_agent = CharacterAgent()
            char_result = await char_agent.run(
                {"artifacts": {"chapters": state.artifacts.chapters}}, llm_adapter)
            if char_result.success:
                state.artifacts.characters = char_result.output.get("characters", [])
                state.pipeline_state.checkpoint_stack.append("char_done")
            else:
                state.errors.append({"agent": "character_agent", "warnings": char_result.warnings})
                state.status = PipelineStatus.ERROR
                await self._persist(state)
                return state

            # Step 3: 场景切分
            state.status = PipelineStatus.SCENE_SEGMENTING
            state.pipeline_state.current_agent = "scene_agent"
            state.pipeline_state.progress = 0.4
            await self._persist(state)

            scene_agent = SceneAgent()
            scene_result = await scene_agent.run(
                {"artifacts": {"chapters": state.artifacts.chapters, "characters": state.artifacts.characters}}, llm_adapter)
            if scene_result.success:
                state.artifacts.scenes = scene_result.output.get("scenes", [])
                state.pipeline_state.checkpoint_stack.append("scene_done")
            else:
                state.errors.append({"agent": "scene_agent", "warnings": scene_result.warnings})
                state.status = PipelineStatus.ERROR
                await self._persist(state)
                return state

            # Step 4: 剧本生成
            state.status = PipelineStatus.SCRIPT_GENERATING
            state.pipeline_state.current_agent = "script_agent"
            state.pipeline_state.progress = 0.6
            await self._persist(state)

            script_agent = ScriptAgent()
            script_result = await script_agent.run(
                {"artifacts": {"chapters": state.artifacts.chapters, "characters": state.artifacts.characters, "scenes": state.artifacts.scenes}}, llm_adapter)
            if script_result.success:
                state.artifacts.script_yaml = json.dumps(script_result.output, ensure_ascii=False, indent=2)
                state.artifacts.adaptation_notes = script_result.output.get("adaptation_notes", [])
                state.pipeline_state.checkpoint_stack.append("script_done")
            else:
                state.errors.append({"agent": "script_agent", "warnings": script_result.warnings})
                state.status = PipelineStatus.ERROR
                await self._persist(state)
                return state

            # Step 5: 校验
            state.status = PipelineStatus.VALIDATING
            state.pipeline_state.current_agent = "validator"
            state.pipeline_state.progress = 0.9
            await self._persist(state)

            screenplay = {"scenes": state.artifacts.scenes, "dramatis_personae": state.artifacts.characters}
            validation = self.validator.validate(screenplay)
            if validation["passed"]:
                state.status = PipelineStatus.COMPLETED
                state.pipeline_state.progress = 1.0
            else:
                state.errors.extend([{"type": "validation", "message": e} for e in validation["errors"]])
                state.status = PipelineStatus.ERROR

            await self._persist(state)
            return state

        except Exception as e:
            state.status = PipelineStatus.ERROR
            state.errors.append({"type": "pipeline_exception", "message": str(e)})
            await self._persist(state)
            return state

    async def _persist(self, state: SessionState):
        try:
            await self.state_store.save(state)
        except Exception:
            pass
