from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    debug: bool = False
    log_level: str = "INFO"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Rate limiting defaults
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # External API (CoinGecko v3 – no key required for free tier)
    coincap_base_url: str = "https://api.coingecko.com/api/v3"  # kept for compat
    coincap_timeout: float = 15.0

    # Cache TTLs (seconds)
    cache_ttl_top: int = 300      # 5 minutes
    cache_ttl_detail: int = 60    # 1 minute
    cache_ttl_history: int = 300  # 5 minutes
    cache_ttl_search: int = 120   # 2 minutes


settings = Settings()
