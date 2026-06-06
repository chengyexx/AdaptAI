"""Happy Path Pipeline + HITL — 线性执行 Parser→Char→Scene→Script→Valid

HITL 策略: 每个 AI Agent 执行后，置信度 < 阈值 → ⏸ 暂停等待人类审阅
状态流转: CREATED→PARSING→CHAR_EXTRACTING→[CHAR_HITL]→CHAR_DONE→SCENE_SEGMENTING→...→COMPLETED
"""

from state.models import SessionState, PipelineStatus
from state.sqlite_store import SQLiteStateStore
from agents.chapter_parser import ChapterParser
from agents.character_agent import CharacterAgent
from agents.scene_agent import SceneAgent
from agents.script_agent import ScriptAgent
from agents.validator import Validator
from llm.factory import AdapterFactory


class HappyPathPipeline:
    """线性 Pipeline + 每节点 HITL 检查点 — 适用于短文本 (<2万字)"""

    AGENT_ORDER = ["chapter_parser", "character_agent", "scene_agent", "script_agent", "validator"]

    def __init__(self, state_store: SQLiteStateStore | None = None, ws_manager=None):
        self.state_store = state_store or SQLiteStateStore()
        self.ws_manager = ws_manager
        self.parser = ChapterParser()
        self.rule_validator = Validator()

    async def execute(self, state: SessionState, resume_from: PipelineStatus | None = None) -> SessionState:
        """执行 Pipeline

        Args:
            state: 会话状态
            resume_from: 从指定检查点恢复（HITL 后继续），None=从头开始
        """
        from datetime import datetime, UTC

        state.updated_at = datetime.now(UTC).isoformat()
        tid = state.thread_id
        start = resume_from or state.status

        if start not in (
            PipelineStatus.CREATED,
            PipelineStatus.CHAR_HITL,
            PipelineStatus.SCENE_HITL,
            PipelineStatus.SCRIPT_HITL,
            PipelineStatus.ERROR,
            PipelineStatus.PAUSED,
        ):
            return state

        workhorse = AdapterFactory.create_workhorse()

        try:
            # ══ Step 1: 章节解析（规则引擎）══
            if start in (PipelineStatus.CREATED,):
                state.status = PipelineStatus.PARSING
                state.pipeline_state.current_agent = "chapter_parser"
                state.pipeline_state.progress = 0.1
                await self._persist(state)
                await self._push_progress(tid, "chapter_parser", 0.1)

                chapters = self.parser.parse(state.artifacts.chapters[0]["text"] if state.artifacts.chapters else "")
                state.artifacts.chapters = chapters
                state.pipeline_state.checkpoint_stack.append("parser_done")
                state.pipeline_state.progress = 0.2
                await self._persist(state)
                await self._push_progress(tid, "chapter_parser", 0.2)
                await self._push_stage_complete(tid, "chapter_parser")
                await self._log(tid, "success", f"章节解析完成: {len(chapters)} 章")

            # ══ Step 2: 角色识别 ══
            if start in (PipelineStatus.CREATED, PipelineStatus.CHAR_HITL,):
                state = await self._run_agent_step(
                    state, workhorse, tid,
                    agent_name="character_agent",
                    agent_class=CharacterAgent,
                    status_active=PipelineStatus.CHAR_EXTRACTING,
                    status_hitl=PipelineStatus.CHAR_HITL,
                    status_done=PipelineStatus.CHAR_DONE,
                    progress_start=0.25,
                    progress_end=0.4,
                    log_msg="角色识别",
                    hitl_reason="请审阅 AI 识别的角色列表",
                    hitl_data_key="characters",
                )
                if state.status in (PipelineStatus.CHAR_HITL, PipelineStatus.ERROR):
                    return state

            # ══ Step 3: 场景切分 ══
            if start in (PipelineStatus.CREATED, PipelineStatus.CHAR_HITL, PipelineStatus.SCENE_HITL,):
                state = await self._run_agent_step(
                    state, workhorse, tid,
                    agent_name="scene_agent",
                    agent_class=SceneAgent,
                    status_active=PipelineStatus.SCENE_SEGMENTING,
                    status_hitl=PipelineStatus.SCENE_HITL,
                    status_done=PipelineStatus.SCENE_DONE,
                    progress_start=0.45,
                    progress_end=0.6,
                    log_msg="场景切分",
                    hitl_reason="请审阅 AI 切分的场景列表",
                    hitl_data_key="scenes",
                )
                if state.status in (PipelineStatus.SCENE_HITL, PipelineStatus.ERROR):
                    return state

            # ══ Step 4: 剧本生成 ══
            if start in (PipelineStatus.CREATED, PipelineStatus.CHAR_HITL, PipelineStatus.SCENE_HITL, PipelineStatus.SCRIPT_HITL,):
                state = await self._run_agent_step(
                    state, workhorse, tid,
                    agent_name="script_agent",
                    agent_class=ScriptAgent,
                    status_active=PipelineStatus.SCRIPT_GENERATING,
                    status_hitl=PipelineStatus.SCRIPT_HITL,
                    status_done=PipelineStatus.SCRIPT_DONE,
                    progress_start=0.65,
                    progress_end=0.8,
                    log_msg="剧本生成",
                    hitl_reason="请审阅 AI 生成的剧本 YAML",
                    hitl_data_key="script",
                )
                if state.status in (PipelineStatus.SCRIPT_HITL, PipelineStatus.ERROR):
                    return state

            # ══ Step 5: 校验 ══
            state.status = PipelineStatus.VALIDATING
            state.pipeline_state.current_agent = "validator"
            state.pipeline_state.progress = 0.9
            await self._persist(state)
            await self._push_progress(tid, "validator", 0.9)
            await self._log(tid, "info", "校验剧本完整性...")

            screenplay = {"scenes": state.artifacts.scenes, "dramatis_personae": state.artifacts.characters}
            validation = self.rule_validator.validate(screenplay)
            if validation["passed"]:
                state.status = PipelineStatus.COMPLETED
                state.pipeline_state.progress = 1.0
            else:
                state.errors.extend([{"type": "validation", "message": e} for e in validation["errors"]])
                state.status = PipelineStatus.ERROR

            await self._persist(state)

            if state.status == PipelineStatus.COMPLETED:
                await self._push_complete(tid, state)
                await self._log(tid, "success", "剧本生成完成！")
            else:
                await self._push_error(tid, "validator", "; ".join(validation.get("errors", [])))

            return state

        except Exception as e:
            state.status = PipelineStatus.ERROR
            state.errors.append({"type": "pipeline_exception", "message": str(e)})
            await self._persist(state)
            await self._push_error(tid, state.pipeline_state.current_agent or "pipeline", str(e))
            return state

    # ═══════════════════════════════════════════════════════
    # Agent Step Runner — 统一的 Agent 执行 + HITL 检查
    # ═══════════════════════════════════════════════════════

    async def _run_agent_step(
        self, state, llm_adapter, tid,
        agent_name, agent_class, status_active, status_hitl, status_done,
        progress_start, progress_end, log_msg, hitl_reason, hitl_data_key,
    ):
        """通用 Agent 执行步骤：运行 → 检查置信度 → 暂停/继续"""
        from config import settings

        state.status = status_active
        state.pipeline_state.current_agent = agent_name
        state.pipeline_state.progress = progress_start
        await self._persist(state)
        await self._push_progress(tid, agent_name, progress_start)
        await self._log(tid, "info", f"{log_msg}中...")

        agent = agent_class()
        result = await agent.run(
            {"artifacts": {
                "chapters": state.artifacts.chapters,
                "characters": state.artifacts.characters,
                "scenes": state.artifacts.scenes,
            }},
            llm_adapter,
        )

        if not result.success:
            state.errors.append({"agent": agent_name, "warnings": result.warnings})
            state.status = PipelineStatus.ERROR
            await self._persist(state)
            await self._push_error(tid, agent_name, "; ".join(result.warnings) if result.warnings else f"{log_msg}失败")
            return state

        # 写入 Agent 输出
        output = result.output
        if agent_name == "character_agent":
            state.artifacts.characters = output.get("characters", [])
        elif agent_name == "scene_agent":
            state.artifacts.scenes = output.get("scenes", [])
        elif agent_name == "script_agent":
            import json
            state.artifacts.script_yaml = json.dumps(output, ensure_ascii=False, indent=2)

        state.pipeline_state.checkpoint_stack.append(f"{agent_name}_done")

        # HITL 检查: 置信度 < 阈值 → 暂停
        if result.confidence < settings.hitl_confidence_threshold:
            state.status = status_hitl
            state.pipeline_state.progress = progress_end
            await self._persist(state)
            await self._push_progress(tid, agent_name, progress_end)

            if self.ws_manager:
                # 提取可编辑数据
                hitl_data = {}
                if hitl_data_key == "characters":
                    hitl_data = {"characters": state.artifacts.characters}
                elif hitl_data_key == "scenes":
                    hitl_data = {"scenes": state.artifacts.scenes}
                elif hitl_data_key == "script":
                    hitl_data = {"script_yaml": state.artifacts.script_yaml}

                await self.ws_manager.send_hitl_pause(
                    tid, agent_name,
                    data=hitl_data,
                    reason=f"{hitl_reason} (置信度: {result.confidence:.0%})",
                    confidence=result.confidence,
                )

            await self._log(tid, "warn", f"⏸ {log_msg} HITL: 置信度 {result.confidence:.0%} < 阈值 {settings.hitl_confidence_threshold}")
            return state

        # 置信度足够 → 自动通过
        state.status = status_done
        state.pipeline_state.progress = progress_end
        await self._persist(state)
        await self._push_progress(tid, agent_name, progress_end)
        await self._push_stage_complete(tid, agent_name)
        await self._log(tid, "success", f"{log_msg}完成 (置信度: {result.confidence:.0%})")
        return state

    # ═══════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════

    async def _persist(self, state):
        try:
            await self.state_store.save(state)
        except Exception:
            pass

    async def _push_progress(self, tid, agent, percent):
        if self.ws_manager:
            try:
                await self.ws_manager.send_progress(tid, agent, percent)
            except Exception:
                pass

    async def _push_stage_complete(self, tid, agent):
        if self.ws_manager:
            try:
                await self.ws_manager.send_stage_complete(tid, agent, {"agent": agent})
            except Exception:
                pass

    async def _push_error(self, tid, agent, message):
        if self.ws_manager:
            try:
                await self.ws_manager.send_error(tid, agent, message, recoverable=True)
            except Exception:
                pass

    async def _push_complete(self, tid, state):
        if self.ws_manager:
            try:
                await self.ws_manager.send_complete(tid, {
                    "thread_id": state.thread_id,
                    "status": state.status.value,
                    "script_yaml": state.artifacts.script_yaml,
                    "characters": state.artifacts.characters,
                    "scenes": state.artifacts.scenes,
                })
            except Exception:
                pass

    async def _log(self, tid, level, message):
        if self.ws_manager:
            try:
                await self.ws_manager._broadcast(tid, {
                    "type": "log",
                    "level": level,
                    "message": message,
                })
            except Exception:
                pass
