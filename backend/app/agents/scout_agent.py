"""Scout Agent — 全局扫描阶段: 快速通读章节，提取核心人物表和地点表"""

from pathlib import Path
from .base import BaseAgent, AgentResult


class ScoutAgent(BaseAgent):
    """全局扫描 Agent — 通读所有章节，提取角色 + 地点

    输出:
      - characters: 全局核心人物表 (含 id, name, aliases, description, role, importance)
      - locations:  主要地点表 (含 id, name, type, description, key_scenes)
      - story_summary: 剧情走向摘要
    """

    agent_id = "scout_agent"
    confidence_threshold = 0.6

    def __init__(self):
        template_dir = (
            Path(__file__).parent.parent
            / "prompts" / "templates" / "scout_agent" / "v1"
        )
        self.system_template = (template_dir / "system.txt").read_text(encoding="utf-8")
        self.user_template = (template_dir / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        chapters = artifacts.get("chapters", [])

        # 每章取前 2500 字符
        chapter_texts = "\n\n---\n\n".join(
            f"## {c.get('title', 'N/A')} (约 {c.get('char_count', 0)} 字)\n{c.get('text', '')[:2500]}"
            for c in chapters
        )
        return self.system_template, self.user_template.format(
            chapter_texts=chapter_texts
        )

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)

        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
                output = self._extract_json(response.text)

                # 规范化角色
                characters = output.get("characters", [])
                for i, c in enumerate(characters):
                    if "id" not in c:
                        c["id"] = f"c{i + 1}"

                # 规范化地点
                locations = output.get("locations", [])
                for i, loc in enumerate(locations):
                    if "id" not in loc:
                        loc["id"] = f"l{i + 1}"

                # 置信度
                schema_score = self._check_schema(output, ["characters", "locations"])
                sa = output.get("self_assessment", {})
                sa_score = (sa.get("completeness", 5) + sa.get("accuracy", 5)) / 20.0
                confidence = self.compute_confidence(
                    output, state, schema_score, sa_score, 0.8
                )

                return AgentResult(
                    agent_id=self.agent_id,
                    success=len(characters) > 0,
                    output={
                        "characters": characters,
                        "locations": locations,
                        "story_summary": output.get("story_summary", ""),
                    },
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
