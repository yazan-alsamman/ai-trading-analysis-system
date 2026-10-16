"""API_DOCS_ENABLED: empty = automatic (off in production), true / false force docs on / off."""

import pytest

from app.core.config import Settings

SECRET = "x" * 48  # production refuses short JWT secrets


@pytest.mark.parametrize(
    ("environment", "value", "expected"),
    [
        ("development", None, True),
        ("development", "", True),
        ("development", "true", True),
        ("development", "false", False),
        ("production", None, False),
        ("production", "", False),
        ("production", "true", True),
        ("production", "false", False),
    ],
)
def test_docs_enabled(monkeypatch, environment, value, expected):
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    if value is not None:
        monkeypatch.setenv("API_DOCS_ENABLED", value)  # as the .env line would set it
    settings = Settings(_env_file=None, environment=environment, jwt_secret=SECRET)
    assert settings.docs_enabled is expected
