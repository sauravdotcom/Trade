from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trade Signal AI"
    env: str = "dev"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    encryption_key: str = "R4x5eG6w4bG6I8d_jw9NiMm1hrx2VyEmBnHClQpcD4A="

    postgres_url: str = "postgresql+asyncpg://trade:trade@db:5432/trade"
    redis_url: str = "redis://redis:6379/0"

    default_index: str = "NIFTY"
    watchlist: list[str] | str = "NIFTY,BANKNIFTY"
    market_refresh_seconds: int = 3
    nse_timezone: str = "Asia/Kolkata"
    nse_market_open: str = "09:15"
    nse_market_close: str = "15:30"
    use_nse_public_feed: bool = True
    allow_mock_fallback: bool = False
    min_signal_confidence: float = 90.0
    daily_max_calls: int = 4
    call_cooldown_minutes: int = 35
    adaptive_learning_enabled: bool = True
    adaptive_lookback_days: int = 30
    adaptive_min_closed_trades: int = 12
    adaptive_learning_interval_minutes: int = 30
    adaptive_confidence_floor: float = 88.0
    adaptive_confidence_ceiling: float = 96.0
    capital: float = 100000.0
    max_risk_per_trade: float = 0.02

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    kite_api_key: str | None = None
    kite_access_token: str | None = None

    angel_api_key: str | None = None
    angel_client_code: str | None = None
    angel_password: str | None = None
    angel_totp_secret: str | None = None

    upstox_api_key: str | None = None
    upstox_access_token: str | None = None

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    alert_email_to: str | None = None

    allowed_origins: list[str] | str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return ["http://localhost:3000"]

    @field_validator("watchlist", mode="before")
    @classmethod
    def split_watchlist(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return [item.upper() for item in value]
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        return ["NIFTY", "BANKNIFTY"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
