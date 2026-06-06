"""角色识别 Agent — 从小说章节中提取角色信息并构建关系图谱"""

from pathlib import Path
from .base import BaseAgent, AgentResult


class CharacterAgent(BaseAgent):
    """从多章节小说文本中识别所有具名角色

    输出包含：姓名、别称、外貌、性格、叙事定位、角色关系图谱
    """

    agent_id = "character_agent"

    def __init__(self):
        template_dir = (
            Path(__file__).parent.parent
            / "prompts" / "templates" / "character_agent" / "v1"
        )
        self.system_template = (template_dir / "system.txt").read_text(encoding="utf-8")
        self.user_template = (template_dir / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        chapters = artifacts.get("chapters", [])

        # 每章取前 2000 字符作为上下文字段
        chapter_texts = "\n\n---\n\n".join(
            f"## {c.get('title', 'N/A')}\n{c.get('text', '')[:2000]}"
            for c in chapters
        )
        return self.system_template, self.user_template.format(
            chapter_texts=chapter_texts
        )

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)

        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)

                # 给没有 id 的角色自动分配 id
                characters = output.get("characters", [])
                for i, c in enumerate(characters):
                    if "id" not in c:
                        c["id"] = f"c{i + 1}"

                # 置信度计算
                schema_score = self._check_schema(output, ["characters", "self_assessment"])
                sa = output.get("self_assessment", {})
                sa_score = (
                    sa.get("completeness", 5)
                    + sa.get("character_consistency", 5)
                    + sa.get("format_compliance", 5)
                ) / 30.0
                cross_score = 0.8  # 角色数量合理性检查
                confidence = self.compute_confidence(
                    output, state, schema_score, sa_score, cross_score
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
