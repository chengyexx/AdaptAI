"""LLM Provider 工厂 — 根据配置创建对应的 Adapter 实例

双模型策略:
- create_workhorse() → deepseek-chat   (主力: 角色/场景/剧本)
- create_reasoner()  → deepseek-reasoner (大脑: 深度校验)
"""

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
        """从环境变量/配置文件自动创建 Adapter（默认用 Workhorse）"""
        from config import settings
        return cls.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )

    # ── 双模型快捷方法 ──

    @classmethod
    def create_workhorse(cls) -> LLMAdapter:
        """创建 Workhorse 适配器 (deepseek-chat)

        适用节点: Character Agent / Scene Agent / Script Agent
        特点: 128K 上下文、Context Caching、结构化输出稳定
        """
        from config import settings
        return cls.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )

    @classmethod
    def create_reasoner(cls) -> LLMAdapter:
        """创建 Reasoner 适配器 (deepseek-reasoner)

        适用节点: Validator 深度校验
        特点: 强化学习推理、CoT 思维链、逻辑矛盾检测
        """
        from config import settings
        return cls.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_reasoner_model,
        )
