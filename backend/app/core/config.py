from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRETS = {"change-me", ""}
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://trading:trading@localhost:5432/trading"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 14
    first_admin_email: str | None = None
    first_admin_password: str | None = None
    ai_service_url: str = "http://localhost:8001"
    # WebSocket hub (/ws/market)
    ws_heartbeat_seconds: float = 25
    ws_idle_timeout_seconds: float = 75
    ws_queue_size: int = 256
    ws_max_subscriptions: int = 50
    ws_max_message_bytes: int = 4096
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _check_production_secret(self) -> "Settings":
        if self.environment == "production" and (
            self.jwt_secret in INSECURE_JWT_SECRETS or len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET is insecure: in production it must not be 'change-me' and must be "
                f"at least {MIN_JWT_SECRET_LENGTH} characters long. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
