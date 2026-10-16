"""Logging helpers."""

import logging
import re

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
