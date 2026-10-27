"""The secrets-in-logs scanner (scripts/check_log_secrets.py) finds each kind of secret."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_log_secrets", Path(__file__).resolve().parents[1] / "scripts" / "check_log_secrets.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_scanner_finds_secrets() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9x.eyJzdWIiOiIxMjM0NTY3ODkwIn0x.abcdefghijklmnopqrstuvwxyz"
    lines = {
        "JWT": f"token {jwt}",
        "API key": "key tk_ab12cd34_" + "x" * 43,
        "Telegram bot token": "https://api.telegram.org/bot123456:" + "A" * 35 + "/sendMessage",
        "password": "login Passw0rd123",
        "Authorization header": "headers {'authorization': 'Bearer " + "y" * 30 + "'}",
        "private key": "-----BEGIN PRIVATE KEY-----",
        "Google API key": "x-goog-api-key: AIza" + "Q" * 35,  # Y14: GEMINI_API_KEY
    }
    for name, line in lines.items():
        assert name in checker.scan(line), name
    assert checker.scan("GET /ws/market?token=[redacted] 101 user=42") == {}
