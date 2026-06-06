"""剧本生成 Agent — 基于角色表和场景列表生成完整剧本 YAML（含对白/情绪/镜头/改编建议）"""

import json
from pathlib import Path
from .base import BaseAgent, AgentResult


class ScriptAgent(BaseAgent):
    """将角色表+场景列表转化为完整剧本，生成对白、动作、镜头建议、改编备注"""

    agent_id = "script_agent"

    def __init__(self):
        base = (
            Path(__file__).parent.parent
            / "prompts" / "templates" / "script_agent" / "v1"
        )
        self.system_template = (base / "system.txt").read_text(encoding="utf-8")
        self.user_template = (base / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        characters = artifacts.get("characters", [])
        scenes = artifacts.get("scenes", [])

        # 角色表的 JSON 摘要
        char_table = json.dumps(
            [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "aliases": c.get("aliases", []),
                    "role": c.get("description", {}).get("role", ""),
                }
                for c in characters
            ],
            ensure_ascii=False,
            indent=2,
        )
        # 场景列表的 JSON 摘要
        scene_list = json.dumps(
            [
                {
                    "scene_id": s.get("scene_id"),
                    "chapter": s.get("chapter"),
                    "heading": s.get("heading"),
                    "characters_present": s.get("characters_present", []),
                    "mood": s.get("mood", ""),
                    "summary": s.get("summary", ""),
                }
                for s in scenes
            ],
            ensure_ascii=False,
            indent=2,
        )

        return self.system_template, self.user_template.format(
            character_table=char_table, scene_list=scene_list
        )

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)

        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)

                schema_score = self._check_schema(
                    output, ["scenes"]
                )
                sa = output.get("self_assessment", {})
                sa_score = (
                    sa.get("completeness", 5)
                    + sa.get("dialogue_quality", 5)
                    + sa.get("format_compliance", 5)
                ) / 30.0
                confidence = self.compute_confidence(
                    output, state, schema_score, sa_score, 0.8
                )

                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    output=output,
                    confidence=confidence,
                    token_usage=response.token_usage.get("output", 0),
                    retries_used=attempt,
                )

            except Exception as e:
                if attempt == self.max_retries - 1:
                    return AgentResult(
                        agent_id=self.agent_id,
                        success=False,
                        output={},
                        confidence=0.0,
                        retries_used=attempt,
                        warnings=[str(e)],
                    )

        return AgentResult(
            agent_id=self.agent_id, success=False, output={}, confidence=0.0
        )
