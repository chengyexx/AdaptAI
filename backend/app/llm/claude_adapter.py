"""Claude Adapter — 基于 Anthropic SDK"""

import json
from typing import AsyncIterator
from .adapter import LLMAdapter, LLMResponse


class ClaudeAdapter:
    """Claude API 适配器，支持流式和非流式调用"""

    model_name: str
    context_window: int = 200000

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        if not api_key:
            raise ValueError("Claude API key 不能为空")
        self.model_name = model
        self.api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)

    async def close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._ensure_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs = dict(
            model=self.model_name,
            max_tokens=8192,
            messages=messages,
            temperature=temperature,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._client.messages.create(**kwargs)
        text = response.content[0].text

        parsed = None
        if output_schema:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = self._extract_json(text)

        return LLMResponse(
            text=text,
            model=self.model_name,
            token_usage={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
            parsed_output=parsed,
        )

    async def complete_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        self._ensure_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs = dict(
            model=self.model_name,
            max_tokens=8192,
            messages=messages,
            temperature=temperature,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text

    def token_count(self, text: str) -> int:
        # 粗略估计，Claude 约 1 token ≈ 3.5 字符（中文约 1.5 字符/token）
        return len(text) // 3

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON，用于 output_schema 回退解析"""
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
