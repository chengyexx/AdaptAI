"""LLM Adapter 抽象协议 + 统一响应模型"""

from dataclasses import dataclass, field
from typing import Protocol, AsyncIterator, runtime_checkable


@dataclass
class LLMResponse:
    """LLM 调用的统一返回结构"""
    text: str                              # 原始响应文本
    model: str                             # 实际使用的模型名
    token_usage: dict = field(default_factory=dict)  # {input, output}
    parsed_output: dict | None = None      # 结构化输出（当传入 output_schema 时）


@runtime_checkable
class LLMAdapter(Protocol):
    """LLM 适配器协议 — 所有 Provider 实现此接口即可接入系统"""

    model_name: str
    context_window: int

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """非流式调用，返回完整响应"""
        ...

    async def complete_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """流式调用，逐个产出 token 字符串"""
        ...

    def token_count(self, text: str) -> int:
        """估算文本的 token 数"""
        ...
