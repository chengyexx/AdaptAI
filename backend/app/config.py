from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从 .env 文件和环境变量加载

    双模型策略:
    - Workhorse (deepseek-chat):  主力干活模型，128K 上下文 + Context Caching
    - Reasoner  (deepseek-reasoner): R1 推理大脑，CoT 反思校验
    """

    # ── LLM 通用配置 ──
    llm_provider: str = "deepseek"
    llm_api_key: str = ""

    # ── 主力模型 (Workhorse) ──
    # 用于: Character Agent / Scene Agent / Script Agent
    # 特点: 128K 上下文、极致性价比、结构化输出稳定
    llm_model: str = "deepseek-chat"

    # ── 推理模型 (Reasoner / Brain) ──
    # 用于: Validator 深度校验
    # 特点: 强化学习推理、CoT 思维链、逻辑矛盾检测
    llm_reasoner_model: str = "deepseek-reasoner"

    # ── 超参 ──
    llm_workhorse_temperature: float = 0.7
    llm_reasoner_temperature: float = 0.0    # R1 推理模型建议低温甚至 0
    llm_max_tokens: int = 8192

    # ── HITL 与重试 ──
    hitl_confidence_threshold: float = 0.7
    max_retries: int = 3

    # ── 存储 ──
    database_path: str = "data/state.db"
    data_dir: str = "data"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
