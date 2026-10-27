"""End-to-end tests against the running compose stack, through Nginx, with real Celery workers
and beat (``docker compose up``). Not part of the unit tests (``pytest tests_e2e``).

Environment:
- ``E2E_BASE_URL`` (default ``http://localhost``): Nginx;
- ``E2E_ADMIN_EMAIL`` / ``E2E_ADMIN_PASSWORD``: an admin of the stack (CI sets
  ``FIRST_ADMIN_EMAIL`` / ``FIRST_ADMIN_PASSWORD`` in the stack's .env to the same values);
- ``E2E_PURGE`` (default ``docker compose exec -T backend python -m app.cli purge-demo``): how
  the run's accounts and market are removed at the end; empty disables the clean-up.
- ``E2E_COMPOSE`` (default ``docker compose``): how the AI steps reach the stack, to queue a
  task the way beat does (``celery call`` in the ``beat`` container), drive the fakes and
  recreate the backend with chart analysis off;
- ``E2E_REQUIRE_FAKES`` (CI: ``1``): the AI steps (09 to 11) fail instead of skipping when the
  stack runs without the fakes (``AI_EVALUATE_ENABLED``, ``AI_SERVICE_URL=http://fake-ai:8001``,
  ``GEMINI_API_KEY``, ``CHART_VISION_BASE_URL=http://fake-gemini:8002``; see the ``e2e`` job).

Every account is ``e2e-<run>-<role>@example.com`` and the markets ``E2E<run>…/USDT``, so a run
never touches other data and the clean-up removes exactly what it made. A step that waits waits
on a condition with a timeout (:func:`wait_for`), never a fixed sleep.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import websockets

BASE = os.environ.get("E2E_BASE_URL", "http://localhost").rstrip("/")
API = f"{BASE}/api/v1"
WS = BASE.replace("http", "ws", 1) + "/ws/market"
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "Passw0rd123")
PASSWORD = "E2e-Passw0rd-123"
RUN = uuid.uuid4().hex[:6]
ROOT = Path(__file__).resolve().parents[2]
COMPOSE = os.environ.get("E2E_COMPOSE", "docker compose")
REQUIRE_FAKES = os.environ.get("E2E_REQUIRE_FAKES", "").lower() in ("1", "true", "yes")
MINUTE = timedelta(minutes=1)


@dataclass
class Account:
    email: str
    token: str
    id: str
    refresh: str = ""

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class World:
    """What the steps create and share (the steps run in file order)."""

    admin: Account | None = None
    users: dict[str, Account] = field(default_factory=dict)
    instrument_id: str = ""
    data: dict = field(default_factory=dict)


def pytest_collection_modifyitems(items):
    items.sort(key=lambda i: i.fspath.basename)  # step files run in order


@pytest.fixture(scope="session")
def world() -> World:
    return World()


@pytest.fixture(scope="session")
def http():
    with httpx.Client(base_url=API, timeout=30) as client:
        yield client


def login(http: httpx.Client, email: str, password: str) -> Account:
    res = http.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    body = res.json()
    me = http.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    return Account(email, body["access_token"], me.json()["id"], body["refresh_token"])


def register(http: httpx.Client, role: str) -> str:
    email = f"e2e-{RUN}-{role}@example.com"
    res = http.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": f"E2E {role.capitalize()}"},
    )
    assert res.status_code == 201, res.text
    return email


def _ready(res: httpx.Response) -> bool:
    try:
        body = res.json()
    except ValueError:  # e.g. Nginx's HTML 502 while the backend is still starting
        return False
    return res.status_code == 200 and isinstance(body, dict) and body.get("status") == "ok"


def wait_until_ready(http: httpx.Client, timeout: float = 120, every: float = 2) -> None:
    """Until ``/health/ready`` answers 200 with ``{"status": "ok"}``. Anything else (connection
    refused, Nginx's 502 HTML, a 503, a ``degraded`` body) means not ready yet. On timeout the
    error names the last answer."""
    deadline = time.time() + timeout
    attempts, last = 0, "no answer"
    while True:
        attempts += 1
        try:
            res = http.get("/health/ready")
            if _ready(res):
                if attempts > 1:
                    print(f"\nstack ready after {attempts} probes")
                return
            last = f"HTTP {res.status_code}: {res.text[:200]!r}"
        except httpx.HTTPError as exc:
            last = f"{type(exc).__name__}: {str(exc)[:200]}"
        if time.time() > deadline:
            raise RuntimeError(f"stack not ready at {API} after {timeout:g} s; last answer: {last}")
        time.sleep(every)


@pytest.fixture(scope="session", autouse=True)
def stack(http: httpx.Client, world: World):
    """Wait for the stack, log in the admin, clean up the run's data at the end."""
    wait_until_ready(http)
    world.admin = login(http, ADMIN_EMAIL, ADMIN_PASSWORD)
    yield
    purge = os.environ.get(
        "E2E_PURGE", "docker compose exec -T backend python -m app.cli purge-demo"
    )
    if purge:
        cmd = [*shlex.split(purge), "--prefix", f"e2e-{RUN}-", "--instrument-prefix", f"E2E{RUN}"]
        out = subprocess.run([*cmd, "--yes"], cwd=ROOT, capture_output=True, text=True)
        print(f"\nclean-up: {out.stdout.strip() or out.stderr.strip()}")


@pytest.fixture(scope="session")
def make_account(http: httpx.Client, world: World):
    """A fresh account of a role (registered, then promoted by the admin)."""

    def _make(role: str) -> Account:
        if role in world.users:
            return world.users[role]
        email = register(http, role)
        account = login(http, email, PASSWORD)
        if role in ("analyst", "expert", "admin"):
            res = http.patch(
                f"/admin/users/{account.id}/role", json={"role": role}, headers=world.admin.h
            )
            assert res.status_code == 200, res.text
        world.users[role] = account
        return account

    return _make


# --- the stack: Celery tasks, the fakes, conditions ----------------------------------------------


def compose(*args: str, env: dict[str, str | None] | None = None, timeout: float = 180) -> str:
    """``docker compose <args>`` in the repository root; its stdout. An error fails the step.
    ``env``: variables for compose's interpolation (``None`` unsets one, so .env decides)."""
    cmd = [*shlex.split(COMPOSE), *args]
    environ = {**os.environ, **(env or {})}
    out = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={k: v for k, v in environ.items() if v is not None},
    )
    assert out.returncode == 0, f"{' '.join(cmd)} failed ({out.returncode}): {out.stderr[-2000:]}"
    return out.stdout


def send_task(name: str, *args: Any) -> None:
    """Queue a Celery task the way beat does (through the broker, with beat's routing), from the
    ``beat`` container, instead of waiting for its schedule."""
    compose(
        "exec", "-T", "beat", "celery", "-A", "app.tasks", "call", name, "--args", json.dumps(args)
    )


# a control call to a fake from inside its own container (the fakes publish no port)
_FAKE_CALL = (
    "import sys, urllib.request; "
    "body = sys.argv[2].encode() if len(sys.argv) > 2 else None; "
    "r = urllib.request.Request(sys.argv[1], data=body, "
    "headers={'Content-Type': 'application/json'}); "
    "print(urllib.request.urlopen(r, timeout=10).read().decode())"
)


def fake(service: str, port: int, path: str, body: dict | None = None) -> Any:
    """``GET`` (no body) or ``POST`` (a body, ``{}`` for none) to ``service``'s ``/_fake/...``."""
    url = [f"http://127.0.0.1:{port}{path}"] + ([json.dumps(body)] if body is not None else [])
    return json.loads(compose("exec", "-T", service, "python", "-c", _FAKE_CALL, *url))


def wait_for(check: Callable[[], Any], what: str, timeout: float = 60, every: float = 1) -> Any:
    """Poll ``check`` until it returns something truthy, and return that; fail after
    ``timeout`` seconds naming ``what``."""
    deadline = time.time() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.time() > deadline:
            raise AssertionError(f"timed out after {timeout:g} s waiting for {what}")
        time.sleep(every)


def need(enabled: bool, what: str) -> None:
    """Skip the step when a feature is off on this stack (fail instead with
    ``E2E_REQUIRE_FAKES``, as in CI, so a misconfigured job cannot pass by skipping)."""
    if enabled:
        return
    message = f"{what} is off on this stack (the e2e job runs it against the fakes)"
    if REQUIRE_FAKES:
        pytest.fail(message)
    pytest.skip(message)


def system_status(http: httpx.Client, world: World) -> dict:
    res = http.get("/admin/system/status", headers=world.admin.h)
    assert res.status_code == 200, res.text
    return res.json()


# --- markets and candles -------------------------------------------------------------------------


def iso_z(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def this_minute() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0)


def new_market(http: httpx.Client, world: World, suffix: str, **specs: Any) -> tuple[str, str]:
    """``(id, symbol)`` of a new market ``E2E<run><suffix>/USDT`` (removed by the clean-up)."""
    res = http.post(
        "/admin/instruments",
        json={
            "symbol": f"E2E{RUN}{suffix}/USDT",
            "source": "e2e",
            "market": "crypto",
            "price_precision": 2,
            "quantity_precision": 4,
            **specs,
        },
        headers=world.admin.h,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"], res.json()["symbol"]


def bars(start: datetime, closes: list[float | None], *, spread: float | None = None) -> list[dict]:
    """1m candles from ``start``, one minute per close; ``None`` leaves that minute out (a gap).
    Each opens at the previous close."""
    out, prev = [], next(c for c in closes if c is not None)
    for i, close in enumerate(closes):
        if close is None:
            continue
        candle = {
            "ts": (start + i * MINUTE).isoformat(),
            "open": prev,
            "high": round(max(prev, close) + 0.05, 4),
            "low": round(min(prev, close) - 0.05, 4),
            "close": close,
            "volume": 1.0,
        }
        if spread is not None:
            candle["spread"] = spread
        out.append(candle)
        prev = close
    return out


def write_candles(http: httpx.Client, world: World, iid: str, candles: list[dict]) -> None:
    """Through the admin candles API (the path ``simulate-live`` uses), in Nginx-sized batches."""
    for i in range(0, len(candles), 2000):
        chunk = candles[i : i + 2000]
        res = http.post(
            f"/admin/instruments/{iid}/candles", json={"candles": chunk}, headers=world.admin.h
        )
        assert res.status_code == 200 and res.json()["written"] == len(chunk), res.text


# --- WebSocket helpers ---------------------------------------------------------------------------


@asynccontextmanager
async def ws_connect(token: str):
    async with websockets.connect(f"{WS}?token={token}", open_timeout=10) as ws:
        yield ws


async def recv_until(ws, predicate, timeout: float = 10.0) -> dict:
    """The next message matching ``predicate``. Sends ``{"op": "ping"}`` every 20 s while
    waiting: the hub closes connections without a client frame for 75 s (like a real client)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        left = deadline - loop.time()
        if left <= 0:
            raise TimeoutError("expected WebSocket message not received")
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), min(left, 20)))
        except TimeoutError:
            await ws.send('{"op": "ping"}')
            continue
        if predicate(msg):
            return msg


def run(coro):
    return asyncio.run(coro)
