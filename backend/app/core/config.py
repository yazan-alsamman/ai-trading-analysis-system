from functools import lru_cache

from pydantic import field_validator, model_validator
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
    # ai-service client (B7, docs/ai-contract.md): per-attempt timeouts, retries on timeouts,
    # connection errors and 5xx (same body and request_id), bars sent per timeframe
    ai_evaluate_timeout_seconds: float = 10.0
    ai_size_timeout_seconds: float = 5.0
    ai_explain_timeout_seconds: float = 30.0
    ai_max_retries: int = 2
    ai_bars_15m: int = 500
    ai_bars_1h: int = 500
    ai_bars_4h: int = 300
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
    # Subscriptions and payments (Y19). Demo only: no real money, no real provider keys.
    payment_provider: str = "demo"
    payment_demo_webhook_secret: str = ""  # empty: generated once and shared through Redis
    payment_demo_tools: bool = False  # admin fast-forward in production (always on elsewhere)
    payment_return_url: str = ""  # where the demo page sends the browser after paying
    public_base_url: str = ""  # e.g. http://187.127.76.76:8080; empty: from the request (Host)
    platform_fee_pct: float = 20.0  # kept from every paid invoice (expert earnings view)
    subscription_grace_days: int = 3  # past_due keeps access this long, then expired
    checkout_ttl_minutes: int = 30
    # Chat (Y19)
    chat_messages_per_minute: int = 30
    chat_messages_per_day: int = 2000
    chat_edit_window_minutes: int = 15
    chat_notify_collapse_minutes: int = 5  # one external notification per conversation
    # Operations (T05/T07 + hardening)
    log_format: str = "auto"  # auto: JSON when ENVIRONMENT=production, text otherwise | json | text
    app_version: str = "dev"  # the image tag / git sha, baked in at build time (APP_VERSION)
    # Swagger UI, ReDoc and /openapi.json. Empty: on outside production, off in production;
    # true / false force them on / off (e.g. true for a live demo, then back to empty).
    api_docs_enabled: bool | None = None
    # Database connections per process (API and each Celery process). Under overload a request
    # waits db_pool_timeout seconds for a connection, then gets 503 + Retry-After (not a 500).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 10
    # API keys
    api_key_last_used_interval_seconds: int = 60  # last_used_at is written at most this often
    # Data-quality gate (B5, docs/data-quality.md): checked every minute for these instruments
    data_quality_enabled: bool = True
    data_quality_instruments: str = "fxpro:XAU/USD"  # comma list of source:symbol
    data_quality_max_lag_seconds: int = 120  # watermark lag allowed while the market is open
    data_quality_max_missing_pct: float = 1.0  # missing 1m bars over the lookback window
    data_quality_spike_pct: float = 2.0  # largest 1m close-to-close move on the evaluated bar
    # Economic calendar (B6, docs/economic-calendar.md): the ForexFactory weekly JSON, fetched
    # at most once per interval (one request), with a back-off after a 429/403
    calendar_enabled: bool = True
    calendar_ff_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    calendar_fetch_interval_minutes: int = 240
    calendar_fetch_timeout_seconds: float = 15.0  # whole request
    calendar_fetch_max_bytes: int = 2 * 1024 * 1024
    calendar_backoff_hours: float = 6.0  # no request at all for this long after a 429/403
    calendar_currencies: str = "USD"  # default filter of reads and of for_evaluate (comma list)

    @field_validator("api_docs_enabled", mode="before")
    @classmethod
    def _empty_is_auto(cls, value: object) -> object:
        # the deploy appends new keys to the server .env as `KEY=` (empty): that means automatic
        return None if isinstance(value, str) and not value.strip() else value

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
        if "*" in self.cors_origin_list:
            # the API allows credentials: a wildcard would let any site call it as the user
            raise ValueError("CORS_ORIGINS must list the web app origins, not '*'")
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

    @property
    def demo_tools_enabled(self) -> bool:
        """The admin fast-forward of subscriptions: on outside production, or when asked."""
        return self.environment != "production" or self.payment_demo_tools

    @property
    def docs_enabled(self) -> bool:
        """Serve Swagger UI, ReDoc and /openapi.json: API_DOCS_ENABLED when set, otherwise only
        outside production (the public contract is the committed docs/api/openapi.json)."""
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment != "production"

    def price_alert_limit(self, role: str) -> int:
        return getattr(self, f"price_alert_limit_{role}")

    @property
    def data_quality_instrument_list(self) -> list[tuple[str, str]]:
        """``(source, symbol)`` of DATA_QUALITY_INSTRUMENTS (entries without ``:`` are
        ignored), normalised like stored instruments."""
        out = []
        for item in self.data_quality_instruments.split(","):
            source, sep, symbol = item.strip().partition(":")
            if sep and source.strip() and symbol.strip():
                pair = (source.strip().lower(), symbol.strip().upper())
                if pair not in out:
                    out.append(pair)
        return out

    @property
    def ai_bar_counts(self) -> dict[str, int]:
        """Bars per timeframe in an evaluate request, oldest first."""
        return {"15m": self.ai_bars_15m, "1h": self.ai_bars_1h, "4h": self.ai_bars_4h}

    @property
    def calendar_currency_list(self) -> list[str]:
        out = []
        for item in self.calendar_currencies.split(","):
            code = item.strip().upper()
            if code and code not in out:
                out.append(code)
        return out

    @property
    def post_role_set(self) -> frozenset[str]:
        return frozenset(r.strip() for r in self.post_roles.split(",") if r.strip())

    def backtest_quota(self, role: str) -> tuple[int, int]:
        """(concurrent queued + running, per UTC day; 0 = unlimited)."""
        return getattr(self, f"backtest_concurrent_{role}"), getattr(self, f"backtest_daily_{role}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
