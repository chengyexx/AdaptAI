from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从 .env 文件和环境变量加载"""

    # LLM 配置
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-pro"

    # HITL 配置
    hitl_confidence_threshold: float = 0.7
    max_retries: int = 3

    # 存储配置
    database_path: str = "data/state.db"
    data_dir: str = "data"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
