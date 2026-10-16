"""Fakes for the notification channels (no real network in tests): Telegram and FCM through
``httpx.MockTransport``, SMTP through a fake ``smtplib.SMTP``."""

import json
import smtplib
import uuid
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.models.notification import NotificationType, Severity
from app.notifications import service
from app.notifications.channels.push import FcmClient
from app.notifications.channels.telegram import TelegramClient

TOKEN = "123456:TEST-token_ABCDEFGHIJKLMNOPQRSTUV"


class FakeTelegram:
    """Records Telegram API calls; ``responses`` (method -> list of (status, json)) are used
    in order, then ``{"ok": true}``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        self.error: Exception | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.error is not None:
            raise self.error
        method = request.url.path.rsplit("/", 1)[-1]
        self.calls.append((method, json.loads(request.content or b"{}")))
        queued = self.responses.get(method)
        if queued:
            status_code, body = queued.pop(0)
            return httpx.Response(status_code, json=body)
        if method == "getMe":
            return httpx.Response(200, json={"ok": True, "result": {"username": "TradingTestBot"}})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.calls)}})

    def client(self) -> TelegramClient:
        return TelegramClient(token=TOKEN, transport=httpx.MockTransport(self.handler))

    def sent(self) -> list[dict[str, Any]]:
        return [payload for method, payload in self.calls if method == "sendMessage"]


def service_account() -> dict[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return {
        "type": "service_account",
        "client_email": "push@test-project.iam.gserviceaccount.com",
        "private_key": pem,
        "token_uri": "https://oauth2.test/token",
    }


class FakeFcm:
    def __init__(self) -> None:
        self.token_requests = 0
        self.messages: list[dict[str, Any]] = []
        self.headers: list[str] = []
        self.responses: list[tuple[int, dict[str, Any]]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.test":
            self.token_requests += 1
            return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3599})
        self.messages.append(json.loads(request.content))
        self.headers.append(request.headers.get("authorization", ""))
        if self.responses:
            status_code, body = self.responses.pop(0)
            return httpx.Response(status_code, json=body)
        return httpx.Response(200, json={"name": f"projects/p/messages/{len(self.messages)}"})

    def factory(self) -> Callable[[Any], FcmClient]:
        return lambda redis: FcmClient(redis, transport=httpx.MockTransport(self.handler))


class FakeSMTP:
    """Stands in for ``smtplib.SMTP``: records messages, or fails as configured."""

    sent: list[EmailMessage] = []
    fail: Exception | None = None
    connections = 0

    def __init__(self, host: str, port: int, timeout: float) -> None:
        FakeSMTP.connections += 1
        self.timeout = timeout
        if FakeSMTP.fail is not None and isinstance(FakeSMTP.fail, OSError):
            raise FakeSMTP.fail

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def starttls(self, context=None) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        return None

    def send_message(self, message: EmailMessage) -> dict:
        if FakeSMTP.fail is not None:
            raise FakeSMTP.fail
        FakeSMTP.sent.append(message)
        return {}

    @classmethod
    def reset(cls) -> None:
        cls.sent, cls.fail, cls.connections = [], None, 0


def install_smtp(monkeypatch) -> type[FakeSMTP]:
    FakeSMTP.reset()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def item(user_id: uuid.UUID, **over) -> service.NotifyItem:
    data = over.pop("data", {"title": "Hello", "body": "World"})
    return service.NotifyItem(
        user_id=user_id,
        type=over.pop("type", NotificationType.system),
        data=data,
        dedup_key=over.pop("dedup_key", f"test:{uuid.uuid4()}"),
        severity=over.pop("severity", Severity.info),
        **over,
    )


SIGNAL_DATA = {
    "signal": {
        "id": "00000000-0000-4000-8000-000000000001",
        "strategy_key": "ma_crossover",
        "timeframe": "1h",
        "side": "buy",
        "price": 36446.94,
        "strength": 0.42,
    },
    "strategy_name": "Moving Average Crossover",
    "instrument": {"symbol": "BTC/USDT", "price_precision": 2, "quantity_precision": 4},
    "plan": {
        "side": "long",
        "entry_ref": 36446.94,
        "stop": 36365.2218577,
        "targets": [{"price": 36610.3762846, "r": 2.0, "close_pct": 100.0}],
        "quantity": 0.2740973588,
        "notional": 9990.01,
        "risk_amount": 42.3563,
        "risk_pct": 0.4236,
        "rr": 2.0,
        "invalid_reason": None,
        "account_size": 10000.0,
        "quote_currency": "USDT",
    },
}
