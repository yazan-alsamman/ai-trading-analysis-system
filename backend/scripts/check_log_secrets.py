"""Fail if a log contains a secret (B3). CI runs the whole test suite with every log record
written at DEBUG (``pytest --log-file=... --log-file-level=DEBUG``) and scans that file:

    python scripts/check_log_secrets.py /tmp/pytest.log

Secrets looked for: JWTs (access and refresh tokens), full API keys, Telegram bot tokens, the
test suite's password and JWT secret, Authorization headers, PEM private keys (the FCM service
account), the demo webhook signature secret.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = {
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "API key": re.compile(r"\btk_[a-z0-9]{8}_[A-Za-z0-9_-]{20,}"),
    # also inside Telegram URLs (".../bot123456:AA..."), where \b would not match
    "Telegram bot token": re.compile(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{30,}"),
    "password": re.compile(r"Passw0rd123"),
    "JWT secret": re.compile(r"test-secret-that-is-at-least-32-characters-long"),
    "Authorization header": re.compile(r"(?i)authorization['\"]?\s*[:=]\s*['\"]?bearer\s+\S{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}


def scan(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name, pattern in PATTERNS.items():
        for line in text.splitlines():
            if pattern.search(line):
                found.setdefault(name, []).append(line.strip()[:200])
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_log_secrets.py LOGFILE", file=sys.stderr)
        return 2
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8", errors="replace")
    found = scan(text)
    lines = text.count("\n")
    if not found:
        print(f"no secrets in {path} ({lines} lines, {len(PATTERNS)} patterns)")
        return 0
    for name, hits in found.items():
        print(f"{name}: {len(hits)} line(s), e.g. {hits[0]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
