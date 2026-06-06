"""DeepSeek Adapter — 基于 DeepSeek API (兼容 OpenAI 协议)"""

import json
import httpx
from typing import AsyncIterator
from .adapter import LLMAdapter, LLMResponse


class DeepSeekAdapter:
    """DeepSeek API 适配器，支持流式和非流式调用"""

    model_name: str
    context_window: int = 1_000_000

    def __init__(self, api_key: str, model: str = "deepseek-v4-pro"):
        if not api_key:
            raise ValueError("DeepSeek API key 不能为空")
        self.model_name = model
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.deepseek.com/v1",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": temperature,
        }
        if output_schema:
            payload["response_format"] = {"type": "json_object"}

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        text = data["choices"][0]["message"]["content"]

        parsed = None
        if output_schema:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = self._extract_json(text)

        return LLMResponse(
            text=text,
            model=self.model_name,
            token_usage=data.get("usage", {}),
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
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": temperature,
            "stream": True,
        }
        if output_schema:
            payload["response_format"] = {"type": "json_object"}

        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    def token_count(self, text: str) -> int:
        # 粗略估计，中文约 1 token ≈ 1.5 字符
        return len(text) // 2

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
