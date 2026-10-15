import logging

from app.core.logging import RedactTokenFilter, install_token_redaction, redact_tokens


def test_redact_tokens() -> None:
    assert redact_tokens("/ws/market?token=abc.def.ghi") == "/ws/market?token=[redacted]"
    assert redact_tokens("/x?a=1&token=abc&b=2") == "/x?a=1&token=[redacted]&b=2"
    assert redact_tokens("/api/v1/health") == "/api/v1/health"


def test_filter_redacts_uvicorn_style_records() -> None:
    record = logging.LogRecord(
        "uvicorn.error",
        logging.INFO,
        __file__,
        1,
        '%s - "WebSocket %s" [accepted]',
        ("1.2.3.4:5", "/ws/market?token=eyJhbGciOi.payload.sig"),
        None,
    )
    assert RedactTokenFilter().filter(record)
    assert record.getMessage() == '1.2.3.4:5 - "WebSocket /ws/market?token=[redacted]" [accepted]'


def test_installed_on_uvicorn_loggers() -> None:
    install_token_redaction()
    install_token_redaction()  # idempotent
    for name in ("uvicorn.access", "uvicorn.error"):
        filters = [f for f in logging.getLogger(name).filters if isinstance(f, RedactTokenFilter)]
        assert len(filters) == 1
