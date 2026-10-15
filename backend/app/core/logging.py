"""Logging helpers."""

import logging
import re

_TOKEN_IN_URL = re.compile(r"(token=)[^&\s\"']+")


def redact_tokens(value: str) -> str:
    return _TOKEN_IN_URL.sub(r"\1[redacted]", value)


class RedactTokenFilter(logging.Filter):
    """Hide ``token=...`` query values (the WebSocket access token) in log records."""

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
