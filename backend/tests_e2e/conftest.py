"""End-to-end tests against the running compose stack, through Nginx, with real Celery workers
and beat (``docker compose up``). Not part of the unit tests (``pytest tests_e2e``).

Environment:
- ``E2E_BASE_URL`` (default ``http://localhost``): Nginx;
- ``E2E_ADMIN_EMAIL`` / ``E2E_ADMIN_PASSWORD``: an admin of the stack (CI sets
  ``FIRST_ADMIN_EMAIL`` / ``FIRST_ADMIN_PASSWORD`` in the stack's .env to the same values);
- ``E2E_PURGE`` (default ``docker compose exec -T backend python -m app.cli purge-demo``): how
  the run's accounts and market are removed at the end; empty disables the clean-up.

Every account is ``e2e-<run>-<role>@example.com`` and the market ``E2E<run>/USDT``, so a run
never touches other data and the clean-up removes exactly what it made.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

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
