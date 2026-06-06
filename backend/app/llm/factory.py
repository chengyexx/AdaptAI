"""LLM Provider 工厂 — 根据配置创建对应的 Adapter 实例"""

from .adapter import LLMAdapter


class AdapterFactory:
    """管理已注册的 Provider，提供创建和自动选择能力"""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, provider: str, adapter_cls: type) -> None:
        """注册一个 Provider → Adapter 类的映射"""
        cls._registry[provider] = adapter_cls

    @classmethod
    def create(cls, provider: str, api_key: str, model: str, **kwargs) -> LLMAdapter:
        """根据 provider 名称显式创建 Adapter 实例"""
        if provider not in cls._registry:
            raise ValueError(
                f"未知的 LLM Provider: '{provider}'。"
                f"已注册: {list(cls._registry.keys())}"
            )
        return cls._registry[provider](api_key=api_key, model=model, **kwargs)

    @classmethod
    def from_env(cls) -> LLMAdapter:
        """从环境变量/配置文件自动创建 Adapter（推荐入口）"""
        from ..config import settings
        return cls.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
