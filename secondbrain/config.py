from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_api_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = ""

    supermemory_api_key: str = ""
    supermemory_base_url: str = "https://api.supermemory.ai"

    llamaparse_api_key: str = ""

    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"

    database_url: str = "postgresql://secondbrain:secondbrain@localhost:5432/secondbrain"
    redis_url: str = "redis://localhost:6379/0"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme123"

    spend_cap_usd: float = 5.0
    throttle_per_min: int = 30
    max_concurrent_streams: int = 5

    price_per_1k_input_tokens: float = 0.003
    price_per_1k_output_tokens: float = 0.015
    max_response_tokens_estimate: int = 1000

    cache_similarity_threshold: float = 0.92
    cache_ttl_seconds: int = 3600
    warmup_similarity_threshold: float = 0.85

    upload_quota_bytes_per_day: int = 500 * 1024 * 1024


settings = Settings()
