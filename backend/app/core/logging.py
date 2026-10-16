"""Logging helpers: secret redaction, quiet HTTP clients, and structured logs (request id,
user id, route, status, duration) in JSON or text."""

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime

_TOKEN_IN_URL = re.compile(r"((?:token|api_key)=)[^&\s\"']+")
_TELEGRAM_TOKEN = re.compile(r"bot\d+:[A-Za-z0-9_-]+")  # in Telegram API URLs
_WEBHOOK_SECRET = re.compile(r"(/telegram/webhook/)[^/\s?\"']+")


def redact_tokens(value: str) -> str:
    value = _TOKEN_IN_URL.sub(r"\1[redacted]", value)
    value = _TELEGRAM_TOKEN.sub("bot[redacted]", value)
    return _WEBHOOK_SECRET.sub(r"\1[redacted]", value)


class RedactTokenFilter(logging.Filter):
    """Hide ``token=...`` and ``api_key=...`` query values (WebSocket credentials) in log
    records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_tokens(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_tokens(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_token_redaction() -> None:
    # uvicorn logs request paths (with the query string) on these two loggers
    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokenFilter) for f in logger.filters):
            logger.addFilter(RedactTokenFilter())


def quiet_http_clients() -> None:
    """httpx logs every request URL at INFO, and Telegram's URLs contain the bot token: keep
    those loggers at WARNING everywhere (API, workers, telegram-bot)."""
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_logging(level: int = logging.INFO) -> None:
    """Plain logging for standalone processes (telegram-bot)."""
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    quiet_http_clients()


# --- structured logs (production) ----------------------------------------------------------------

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
REQUEST_FIELDS = ("method", "route", "path", "status", "duration_ms", "client")


class ContextFilter(logging.Filter):
    """Adds the current request id and user id to every record (None outside requests)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        if getattr(record, "user_id", None) is None:
            record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line; the message is redacted like every other log line."""

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_tokens(record.getMessage()),
        }
        for name in ("request_id", "user_id", *REQUEST_FIELDS):
            value = getattr(record, name, None)
            if value is not None:
                out[name] = value
        if record.exc_info:
            out["exc"] = redact_tokens(self.formatException(record.exc_info))
        return json.dumps(out, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        text = redact_tokens(super().format(record))
        extra = " ".join(
            f"{name}={getattr(record, name)}"
            for name in ("request_id", "user_id", *REQUEST_FIELDS)
            if getattr(record, name, None) is not None
        )
        return f"{text} {extra}" if extra else text


def use_json(fmt: str | None = None) -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    fmt = (fmt or settings.log_format).lower()
    return fmt == "json" or (fmt == "auto" and settings.environment == "production")


def setup_logging(level: int = logging.INFO, loggers: tuple[str, ...] = ()) -> None:
    """One handler on the root logger (JSON in production with LOG_FORMAT=auto, text
    elsewhere); ``loggers`` (e.g. uvicorn's) drop their own handlers and propagate to it."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if use_json() else TextFormatter())
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in loggers:
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    quiet_http_clients()
