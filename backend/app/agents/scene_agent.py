"""场景切分 Agent — 将小说章节切分为独立的场景单元并交叉验证角色引用"""

from pathlib import Path
from .base import BaseAgent, AgentResult


class SceneAgent(BaseAgent):
    agent_id = "scene_agent"

    def __init__(self):
        base = Path(__file__).parent.parent / "prompts" / "templates" / "scene_agent" / "v1"
        self.system_template = (base / "system.txt").read_text(encoding="utf-8")
        self.user_template = (base / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        chapters = artifacts.get("chapters", [])
        characters = artifacts.get("characters", [])

        chapter_texts = "\n\n".join(
            f"## {c.get('title', 'N/A')}\n{c.get('text', '')[:3000]}"
            for c in chapters
        )
        char_list = "\n".join(
            f"- {c['id']}: {c['name']}"
            + (f" ({', '.join(c.get('aliases', []))})" if c.get("aliases") else "")
            for c in characters
        )
        return self.system_template, self.user_template.format(
            chapter_texts=chapter_texts, character_list=char_list
        )

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)

        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)

                for i, s in enumerate(output.get("scenes", [])):
                    if "scene_id" not in s:
                        s["scene_id"] = f"s{i + 1}"

                schema_score = self._check_schema(output, ["scenes", "self_assessment"])
                cross_score = self._cross_validate(output, state)
                sa = output.get("self_assessment", {})
                sa_score = (
                    sa.get("segmentation_accuracy", 5)
                    + sa.get("location_identification", 5)
                    + sa.get("character_attendance", 5)
                    + sa.get("format_compliance", 5)
                ) / 40.0
                confidence = self.compute_confidence(output, state, schema_score, sa_score, cross_score)

                return AgentResult(
                    agent_id=self.agent_id, success=True, output=output,
                    confidence=confidence,
                    token_usage=response.token_usage.get("output", 0),
                    retries_used=attempt,
                )
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return AgentResult(
                        agent_id=self.agent_id, success=False, output={},
                        confidence=0.0, retries_used=attempt, warnings=[str(e)],
                    )
        return AgentResult(agent_id=self.agent_id, success=False, output={}, confidence=0.0)

    def _cross_validate(self, output: dict, state: dict) -> float:
        scenes = output.get("scenes", [])
        if not scenes:
            return 0.5
        characters = state.get("artifacts", {}).get("characters", [])
        char_ids = {c["id"] for c in characters}
        if not char_ids:
            return 1.0
        errors = sum(
            1 for s in scenes
            for cid in s.get("characters_present", [])
            if cid not in char_ids
        )
        return max(0.0, 1.0 - errors / max(len(scenes), 1))
