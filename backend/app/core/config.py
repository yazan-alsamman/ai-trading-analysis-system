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
    # Rate limiting (app/core/rate_limit.py). All limits are per minute.
    rate_limit_enabled: bool = True
    rate_limit_key_prefix: str = "rl"  # Redis key prefix of buckets, lockouts and usage
    rate_limit_trader: int = 60
    rate_limit_analyst: int = 300
    rate_limit_expert: int = 300
    rate_limit_admin: int = 1000
    rate_limit_expensive_cost: int = 5  # indicators compute + strategy preview
    auth_login_ip_per_minute: int = 10  # /auth/login and /auth/token
    auth_login_email_per_minute: int = 5
    auth_register_ip_per_minute: int = 5
    auth_refresh_ip_per_minute: int = 30
    login_lockout_failures: int = 10  # failed logins of one email within the window ...
    login_lockout_window_seconds: int = 900
    login_lockout_seconds: int = 900  # ... lock that email for this long
    ws_max_connections_per_identity: int = 5
    ws_new_connections_ip_per_minute: int = 20
    # Workspaces: at most this many per user, by role
    workspace_limit_trader: int = 5
    workspace_limit_analyst: int = 20
    workspace_limit_expert: int = 20
    workspace_limit_admin: int = 20
    # Backtests: queued + running at once, and created per UTC day (0 = unlimited), by role
    backtest_concurrent_trader: int = 2
    backtest_concurrent_analyst: int = 5
    backtest_concurrent_expert: int = 5
    backtest_concurrent_admin: int = 10
    backtest_daily_trader: int = 30
    backtest_daily_analyst: int = 200
    backtest_daily_expert: int = 200
    backtest_daily_admin: int = 0
    backtest_max_bars: int = 200_000
    backtest_time_limit_seconds: int = 300  # Celery soft time limit of one backtest
    # Custom strategies (Y12): at most this many per user, by role
    custom_strategy_limit_trader: int = 5
    custom_strategy_limit_analyst: int = 50
    custom_strategy_limit_expert: int = 50
    custom_strategy_limit_admin: int = 50
    rate_limit_validate_cost: int = 2  # POST /custom-strategies/validate
    # Notifications (Y15). Empty secrets = that channel is disabled (reported, never an error).
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""  # optional: otherwise read once with getMe
    telegram_mode: str = "polling"  # polling (no HTTPS needed) | webhook
    telegram_webhook_secret: str = ""
    telegram_api_base: str = "https://api.telegram.org"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    fcm_project_id: str = ""
    fcm_credentials_json: str = ""  # service-account JSON, or a path to the file
    notification_timeout_seconds: float = 10.0  # every outbound call
    notification_max_attempts: int = 5
    notification_breaker_failures: int = 5  # consecutive failures that open a channel's circuit
    notification_breaker_seconds: int = 300  # how long it stays open
    notification_test_cost: int = 5  # rate-limit cost of POST /me/notifications/test
    # News (Y18). The RSS task only fetches the seeded public feeds an admin left active.
    news_rss_enabled: bool = True
    news_fetch_timeout_seconds: float = 10.0  # per feed, whole request
    news_fetch_max_bytes: int = 2 * 1024 * 1024  # larger feeds are refused
    news_retention_days: int = 180
    # Posts and comments (Y18)
    post_roles: str = "analyst,expert,admin"  # who may publish posts (everyone may comment)
    post_edit_window_hours: int = 24  # authors edit their posts within this time; admins always
    posts_per_day: int = 10  # per user, rolling 24 h
    comments_per_hour: int = 60  # per user, rolling hour
    reports_per_day: int = 20  # per user, rolling 24 h
    content_create_cost: int = 2  # rate-limit cost of POST /posts, comments and reports
    # Price alerts (Y18): active alerts per user, by role
    price_alert_limit_trader: int = 20
    price_alert_limit_analyst: int = 100
    price_alert_limit_expert: int = 100
    price_alert_limit_admin: int = 100
    # API keys
    api_key_last_used_interval_seconds: int = 60  # last_used_at is written at most this often

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

    def tier_limit(self, role: str) -> int:
        """Requests per minute of a role (``trader``, ``analyst``, ``expert``, ``admin``)."""
        return getattr(self, f"rate_limit_{role}")

    def workspace_limit(self, role: str) -> int:
        return getattr(self, f"workspace_limit_{role}")

    def custom_strategy_limit(self, role: str) -> int:
        return getattr(self, f"custom_strategy_limit_{role}")

    def price_alert_limit(self, role: str) -> int:
        return getattr(self, f"price_alert_limit_{role}")

    @property
    def post_role_set(self) -> frozenset[str]:
        return frozenset(r.strip() for r in self.post_roles.split(",") if r.strip())

    def backtest_quota(self, role: str) -> tuple[int, int]:
        """(concurrent queued + running, per UTC day; 0 = unlimited)."""
        return getattr(self, f"backtest_concurrent_{role}"), getattr(self, f"backtest_daily_{role}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
