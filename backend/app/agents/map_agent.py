"""Map Agent — 切片转换阶段: 逐块生成 YAML 场景脚本"""

import yaml
from pathlib import Path
from .base import BaseAgent, AgentResult
from schemas.screenplay import ScriptDocument


class MapAgent(BaseAgent):
    """切片转换 Agent — 携带全局上下文，逐块生成 YAML 场景

    输出: 符合 ScriptDocument schema 的 YAML (由 LLM 生成原始 YAML，Pydantic 校验)
    """

    agent_id = "map_agent"
    confidence_threshold = 0.6

    def __init__(self):
        template_dir = (
            Path(__file__).parent.parent
            / "prompts" / "templates" / "map_agent" / "v1"
        )
        self.system_template = (template_dir / "system.txt").read_text(encoding="utf-8")
        self.user_template = (template_dir / "user.txt").read_text(encoding="utf-8")

    def build_prompt(
        self,
        chunk_text: str,
        characters_context: str,
        locations_context: str,
    ) -> tuple[str, str]:
        return self.system_template, self.user_template.format(
            characters_context=characters_context,
            locations_context=locations_context,
            chunk_text=chunk_text,
        )

    async def run_for_chunk(
        self,
        chunk_text: str,
        characters_context: str,
        locations_context: str,
        llm_adapter,
        chunk_index: int = 0,
    ) -> AgentResult:
        """为单个切片生成场景 YAML"""
        system_prompt, user_prompt = self.build_prompt(
            chunk_text, characters_context, locations_context
        )

        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )

                # 解析 LLM 输出的 YAML
                yaml_text = self._clean_yaml(response.text)
                scenes = self._parse_and_validate(yaml_text)

                if not scenes:
                    if attempt < self.max_retries - 1:
                        continue
                    return AgentResult(
                        agent_id=self.agent_id,
                        success=False,
                        output={"scenes": [], "yaml_text": yaml_text},
                        confidence=0.0,
                        retries_used=attempt,
                        warnings=["YAML 解析或校验失败"],
                    )

                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    output={
                        "scenes": scenes,
                        "yaml_text": yaml_text,
                        "chunk_index": chunk_index,
                    },
                    confidence=0.85,
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

    def _clean_yaml(self, text: str) -> str:
        """清理 LLM 输出的 YAML，去除 markdown 标记"""
        text = text.strip()
        # 去除 ```yaml ... ``` 包裹
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    def _parse_and_validate(self, yaml_text: str) -> list[dict]:
        """解析 YAML 并用 Pydantic 校验，返回 scene dict 列表"""
        try:
            raw = yaml.safe_load(yaml_text)
            if not raw or "场景列表" not in raw:
                return []

            # Pydantic 校验
            doc = ScriptDocument(**raw)
            # 转回 dict（已通过校验）
            return [s.model_dump() for s in doc.场景列表]

        except (yaml.YAMLError, Exception):
            return []

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        """不直接使用此方法，由 Pipeline 按 chunk 调用 run_for_chunk"""
        raise NotImplementedError("MapAgent 应通过 run_for_chunk() 使用，而非 run()")
