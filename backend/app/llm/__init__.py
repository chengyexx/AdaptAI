"""LLM Adapter 抽象层 — 模型无关的 LLM 调用接口"""

from .adapter import LLMAdapter, LLMResponse
from .factory import AdapterFactory
from .claude_adapter import ClaudeAdapter
from .deepseek_adapter import DeepSeekAdapter

# 注册已知 Provider
AdapterFactory.register("claude", ClaudeAdapter)
AdapterFactory.register("deepseek", DeepSeekAdapter)

__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "AdapterFactory",
    "ClaudeAdapter",
    "DeepSeekAdapter",
]
