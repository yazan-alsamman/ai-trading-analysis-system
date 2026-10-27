"""Run every request of spec.py against a running API and save the responses as examples.

Use a local stack with demo data, never production:

    docker compose up -d                      # or uvicorn + a Celery worker on queue "backtests"
    docker compose exec backend python -m app.cli seed-instruments
    docker compose exec backend python -m app.cli seed-demo-candles --symbol BTC/USDT \
        --source binance --days 30
    python docs/postman/tools/capture_examples.py --base-url http://localhost:8000 \
        --admin-email admin@example.com --admin-password '...'

Writes docs/postman/tools/examples.json; then run build_collection.py.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import FOLDERS, Folder, Req, Variant  # noqa: E402

OUT = Path(__file__).resolve().parent / "examples.json"
POSTMAN = Path(__file__).resolve().parents[1]  # files of multipart requests live here
KEEP_HEADERS = {
    "content-type",
    "etag",
    "content-disposition",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "retry-after",
    "x-request-id",
}
# Lists longer than this are cut to TRIM_TO items in saved examples (candles, curves, ...),
# except in the responses below, whose whole content is the point.
TRIM_OVER, TRIM_TO = 6, 3
NO_TRIM = {"indicators_catalog", "strategies_catalog", "keys_scopes"}

CAPTURE_EMAIL = "trader@example.com"
CAPTURE_PASSWORD = "Trader12345"
# A second analyst who publishes a post, so the feed has someone to follow and something to report.
AUTHOR_EMAIL = "lina@example.com"
AUTHOR_PASSWORD = "Analyst12345"
# An expert with a plan (all perks) and a subscribers-only post: the directory, checkout, chat
# and the teaser in the feed need someone to subscribe to.
EXPERT_EMAIL = "sami@example.com"
EXPERT_PASSWORD = "Expert12345"
BACKEND = Path(__file__).resolve().parents[3] / "backend"


AI_SETUP_ID = "xauusd-intraday-2026-10-19T14:15:00Z-buy"  # new_setups[0] of the example
SEED_AI_SETUP = """
import asyncio, json
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select, text
from app.ai import contract as c, explain, store
from app.db.session import SessionLocal
from app.models.instrument import Instrument

EXAMPLES = Path("../docs/api/ai-service-examples")


def load(name):
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


async def main():
    async with SessionLocal() as session:
        gold = await session.scalar(
            select(Instrument).order_by((Instrument.symbol == "XAU/USD").desc(), Instrument.symbol)
        )
        req = c.EvaluateRequest.model_validate(load("evaluate-request"))
        resp = load("evaluate-response-ok")
        resp["transitions"] = []
        first = await store.apply_evaluation(
            session, gold, req, c.EvaluateResponse.model_validate(resp)
        )
        close = req.bar_close_ts + timedelta(minutes=15)
        nxt = req.model_copy(
            update={"request_id": c.make_request_id("XAUUSD", "intraday", close),
                    "bar_close_ts": close}
        )
        setup_id = resp["new_setups"][0]["setup_id"]
        move = {"setup_id": setup_id, "from": "ARMED", "to": "ACTIVE",
                "at": c.iso_z(close - timedelta(minutes=6)), "reason": "entry_filled"}
        second = await store.apply_evaluation(
            session, gold, nxt, c.EvaluateResponse.model_validate(
                {**resp, "request_id": nxt.request_id, "new_setups": [], "transitions": [move]}
            )
        )
        # one failed alert for Admin -> AI Engine -> Retry outbox alert (no dispatch ran)
        await session.execute(
            text(
                "UPDATE ai_setup_outbox SET status = 'failed', attempts = 8, "
                "last_error = 'telegram: 502 Bad Gateway' "
                "WHERE setup_id = :id AND to_state = 'ACTIVE' AND status = 'pending'"
            ),
            {"id": setup_id},
        )
        await session.commit()
        # its Arabic explanation (the contract's example, verified) for AI setup explanation
        await explain.store_answer(
            session, setup_id, "ar", c.ExplainResponse.model_validate(load("explain-response"))
        )
        print(first.inserted, second.transitions_applied)


asyncio.run(main())
"""


# Three ma_crossover signals on BTC/USDT 1h (the demo candles): two whose 10-bar horizon has
# closed, resolved in-process like the beat task (Predictions examples and the admin resolver
# status), and one still open. Fixed params_hash: a re-run inserts nothing twice.
SEED_PREDICTIONS = """
import asyncio
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models.instrument import Instrument
from app.models.strategy import Signal, SignalSide
from app.models.candle import Timeframe
from app.services import market_service, prediction_resolver


async def main():
    async with SessionLocal() as session:
        btc = await session.scalar(select(Instrument).where(Instrument.symbol == "BTC/USDT"))
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        bars = await market_service.candle_range(
            session, btc.id, Timeframe.h1, now - timedelta(hours=72), now
        )
        picks = [(bars[0], "buy", 0.62), (bars[24], "sell", 0.48), (bars[-3], "buy", 0.71)]
        for i, (bar, side, strength) in enumerate(picks):
            await session.execute(
                insert(Signal)
                .values(
                    instrument_id=btc.id, timeframe=Timeframe.h1, strategy_key="ma_crossover",
                    params={"fast": 9, "slow": 21}, params_hash=f"postman-capture-{i}",
                    bar_time=bar[0], side=SignalSide(side), strength=strength, price=float(bar[4]),
                    reason="ema_cross_up" if side == "buy" else "ema_cross_down",
                    details={"fast": 9, "slow": 21},
                    created_at=bar[0] + timedelta(hours=1, seconds=4),
                )
                .on_conflict_do_nothing(constraint="uq_signals_bar")
            )
        await session.commit()
    result = await prediction_resolver.run(SessionLocal, get_redis())
    print(result.resolved, result.gaps)


asyncio.run(main())
"""


def get_path(data: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(data, list):
            if not part.isdigit() or int(part) >= len(data):
                return None
            data = data[int(part)]
        elif isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data


def trim(value: Any, depth: int = 0) -> Any:
    if isinstance(value, list):
        items = value[:TRIM_TO] if len(value) > TRIM_OVER else value
        return [trim(v, depth + 1) for v in items]
    if isinstance(value, dict):
        return {k: trim(v, depth + 1) for k, v in value.items()}
    return value


class Runner:
    def __init__(self, base_url: str, admin_email: str, admin_password: str) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=60)
        self.vars: dict[str, str] = {
            "api_url": "/api/v1",
            "timeframe": "1h",
            "strategy_key": "ma_crossover",
            "user_email": CAPTURE_EMAIL,
            "user_password": CAPTURE_PASSWORD,
            "user_new_password": "Changed12345",
            "register_password": "Postman123",
            "admin_email": admin_email,
            "admin_password": admin_password,
        }
        self.examples: dict[str, list[dict[str, Any]]] = {}

    # --- variables -------------------------------------------------------------------------
    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):

            def sub(m: re.Match[str]) -> str:
                name = m.group(1)
                if name == "$timestamp":
                    return str(int(time.time()))
                if name == "$guid":
                    return str(uuid.uuid4())
                return str(self.vars.get(name, ""))

            return re.sub(r"\{\{([^}]+)\}\}", sub, value)
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        return value

    def typed(self, value: Any) -> Any:
        """``"{{custom_strategy_version}}"`` must reach the API as a number, as in Postman
        where the raw body text is substituted."""
        text = json.dumps(value)
        text = re.sub(
            r'"\{\{(custom_strategy_version)\}\}"',
            lambda m: self.vars[m.group(1)],
            text,
        )
        return json.loads(self.resolve(text)) if isinstance(value, (dict, list)) else value

    # --- auth --------------------------------------------------------------------------------
    def login(self, prefix: str) -> None:
        email = self.vars["admin_email" if prefix else "user_email"]
        password = self.vars["admin_password" if prefix else "user_password"]
        res = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        res.raise_for_status()
        self.vars[f"{prefix}access_token"] = res.json()["access_token"]
        self.vars[f"{prefix}refresh_token"] = res.json()["refresh_token"]

    def auth_headers(self, mode: str) -> dict[str, str]:
        if mode == "none":
            return {}
        if mode == "apikey":
            return {"X-API-Key": self.vars.get("api_key", "")}
        prefix = "admin_" if mode == "admin" else ""
        if not self.vars.get(f"{prefix}access_token"):
            self.login(prefix)
        return {"Authorization": f"Bearer {self.vars[f'{prefix}access_token']}"}

    # --- requests ----------------------------------------------------------------------------
    def send(self, req: Req, variant: Variant | None = None) -> httpx.Response:
        path = variant.path if variant and variant.path else req.path
        pvars = {k: v[0] for k, v in req.path_vars.items()}
        if variant and variant.path_vars:
            pvars.update(variant.path_vars)
        for name, value in pvars.items():
            path = path.replace(f":{name}", self.resolve(value))
        query = {k: self.resolve(v) for k, v, _ in req.query}
        if variant and variant.query is not None:
            query.update(variant.query)
        headers = self.auth_headers(variant.auth if variant and variant.auth else req.auth)
        for k, v, _ in req.headers:
            headers[k] = self.resolve(v)
        if variant and variant.headers:
            for k, v in variant.headers.items():
                if v == "":
                    headers.pop(k, None)
                else:
                    headers[k] = v
        body = variant.body if variant and variant.body is not None else req.body
        kwargs: dict[str, Any] = {"params": query, "headers": headers}
        if req.files is not None:
            files = {k: src for k, src, _ in req.files}
            files.update(variant.files if variant and variant.files else {})
            kwargs["files"] = {
                k: (
                    Path(src).name,
                    (POSTMAN / src).read_bytes(),
                    mimetypes.guess_type(src)[0] or "application/octet-stream",
                )
                for k, src in files.items()
            }
            if req.form is not None:
                kwargs["data"] = {k: self.resolve(v) for k, v, _ in req.form}
        elif req.form is not None:
            kwargs["data"] = {k: self.resolve(v) for k, v, _ in req.form}
        elif isinstance(body, str):
            kwargs["content"] = self.resolve(body)
            headers["Content-Type"] = "application/json"
        elif body is not None:
            kwargs["json"] = self.typed(body)
        return self.http.request(req.method, f"/api/v1{path}", **kwargs)

    def record(self, req: Req, name: str, res: httpx.Response, variant: Variant | None) -> None:
        ctype = res.headers.get("content-type", "")
        if "json" in ctype and res.content:
            body: Any = res.json()
            if req.id not in NO_TRIM:
                body = trim(body)
            text = json.dumps(body, indent=4, ensure_ascii=False)
        else:
            text = res.text
            if req.id == "backtests_trades_csv":
                text = "\n".join(text.splitlines()[: TRIM_TO + 1]) + "\n"
        self.examples.setdefault(req.id, []).append(
            {
                "name": name,
                "code": res.status_code,
                "status": res.reason_phrase,
                "headers": {k: v for k, v in res.headers.items() if k.lower() in KEEP_HEADERS},
                "body": text,
                "variant": None if variant is None else variant.name,
            }
        )

    # --- per-request script equivalents --------------------------------------------------------
    def before(self, req: Req) -> None:
        now = datetime.now(UTC).replace(microsecond=0)
        if req.id == "auth_register":
            self.vars["register_email"] = f"qa.{int(time.time() * 1000)}@example.com"
        if req.id.startswith("backtests_create"):
            end = now - timedelta(hours=1)
            self.vars["backtest_start"] = (end - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.vars["backtest_end"] = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        if req.id == "admin_candles_upsert":
            minute = now.replace(second=0)
            for i, back in enumerate((2, 1, 0)):
                ts = minute - timedelta(minutes=back)
                self.vars[f"candle_ts_{i}"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if req.id == "alerts_history":
            self.fire_price_alert()
        if req.id == "chat_send":
            self.vars["chat_client_id"] = str(uuid.uuid4())
        if req.id == "experts_earnings" and self.vars.get("my_plan_id"):
            self.subscribe(AUTHOR_EMAIL, AUTHOR_PASSWORD, self.vars["my_plan_id"])
        if req.id == "ws_reorder":
            ids = json.loads(self.vars.get("workspace_ids", "[]"))
            self.vars["workspace_ids_reversed"] = json.dumps(list(reversed(ids)))

    def after(self, req: Req, res: httpx.Response) -> None:
        data = res.json() if res.content and "json" in res.headers.get("content-type", "") else None
        if res.status_code < 300 and data is not None:
            for var, path in req.captures.items():
                value = get_path(data, path)
                if value is not None:
                    self.vars[var] = str(value)
        if req.id in ("auth_login", "auth_refresh") and res.status_code == 200:
            self.vars["access_token"] = data["access_token"]
            self.vars["refresh_token"] = data["refresh_token"]
        if req.id == "auth_logout":
            self.vars.pop("refresh_token", None)
        if req.id == "users_me_password" and res.status_code == 204:
            self.vars["user_password"], self.vars["user_new_password"] = (
                self.vars["user_new_password"],
                self.vars["user_password"],
            )
        if req.id == "posts_feed" and data:
            me = self.vars.get("user_id")
            other = [p for p in data["items"] if p["author"]["id"] != me and not p.get("locked")]
            authors = [p for p in other if p["author"]["role"] in ("analyst", "expert")]
            if other:
                self.vars["other_post_id"] = other[0]["id"]
            if authors:
                self.vars["author_user_id"] = authors[0]["author"]["id"]
        if req.id == "experts_list" and data:
            others = [e for e in data["items"] if e["id"] != self.vars.get("user_id")]
            if others:
                self.vars["expert_id"] = others[0]["id"]
        if req.id == "subs_mine" and data:
            mine = [s for s in data if s["expert"]["id"] == self.vars.get("expert_id")]
            if mine:
                self.vars["subscription_id"] = mine[0]["id"]
                if mine[0]["invoices"]:
                    self.vars["invoice_id"] = mine[0]["invoices"][0]["id"]
        if req.id == "alerts_history" and self.vars.get("demo_alert_id"):
            self.http.delete(
                f"/api/v1/me/price-alerts/{self.vars.pop('demo_alert_id')}",
                headers=self.auth_headers("user"),
            )
        if req.id in ("ws_list", "ws_list_2"):
            self.vars["workspace_ids"] = json.dumps([w["id"] for w in data])
        cleanup = {
            "ws_delete": (
                "/me/workspaces/",
                ["workspace_copy_id", "workspace_import_id"],
            ),
            "custom_delete": (
                "/me/custom-strategies/",
                [
                    "custom_strategy_clone_id",
                    "public_clone_id",
                    "composite_strategy_id",
                ],
            ),
            "backtests_delete": ("/backtests/", ["backtest_id_2"]),
        }
        if req.id in cleanup:
            prefix, names = cleanup[req.id]
            for name in names:
                if self.vars.get(name):
                    self.http.delete(
                        f"/api/v1{prefix}{self.vars.pop(name)}",
                        headers=self.auth_headers("user"),
                    )

    def token(self, email: str, password: str) -> dict[str, str]:
        res = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        res.raise_for_status()
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    def subscribe(self, email: str, password: str, plan_id: str) -> None:
        """Another user buys ``plan_id`` with the test card (for the expert's earnings)."""
        res = self.http.post(
            "/api/v1/subscriptions/checkout",
            headers=self.token(email, password),
            json={"plan_id": plan_id},
        )
        if res.status_code != 201:
            print(f"   subscribe {email}: {res.status_code} {res.text[:120]}")
            return
        self.http.post(
            f"/api/v1/pay/demo/{res.json()['checkout_id']}/confirm",
            data={
                "card_number": "4242424242424242",
                "expiry": "12/30",
                "cvc": "123",
                "name": "x",
            },
        )

    def fire_price_alert(self) -> None:
        """A real trigger for the history example: an alert any price meets, a 1m candle for the
        current minute and one evaluation run of the alert engine (in-process, like the worker).
        Needs the backend's environment (DATABASE_URL, REDIS_URL)."""
        res = self.http.post(
            "/api/v1/me/price-alerts",
            headers=self.auth_headers("user"),
            json={
                "instrument_id": self.vars["instrument_id"],
                "condition": "above",
                "value": 1,
                "note": "first target",
            },
        )
        res.raise_for_status()
        self.vars["demo_alert_id"] = res.json()["id"]
        minute = datetime.now(UTC).replace(second=0, microsecond=0)
        price = res.json()["current_price"] or 100.0
        candle = {
            "ts": minute.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": price,
            "high": price * 1.002,
            "low": price * 0.999,
            "close": price * 1.001,
            "volume": 3.2,
        }
        self.http.post(
            f"/api/v1/admin/instruments/{self.vars['instrument_id']}/candles",
            headers=self.auth_headers("admin"),
            json={"candles": [candle]},
        ).raise_for_status()
        code = (
            "from app.tasks.alerts import evaluate; import sys; "
            f"print(evaluate.run({minute.isoformat()!r}))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True
        )
        print(f"   alert engine: {(out.stdout or out.stderr).strip()[-200:]}")

    def seed_ai_setup(self) -> None:
        """An AI setup with two events for the Admin → AI examples: the contract's example
        evaluate response, then the setup going ARMED → ACTIVE (in-process, like the worker),
        its ACTIVE alert marked failed so the outbox retry has a row to retry, and its
        Arabic explanation."""
        out = subprocess.run(
            [sys.executable, "-c", SEED_AI_SETUP], cwd=BACKEND, capture_output=True, text=True
        )
        print(f"   ai setup: {(out.stdout or out.stderr).strip()[-200:]}")
        # the user's AI requests (Risk Management) run before Admin → AI Engine stores the id
        self.vars["ai_setup_id"] = AI_SETUP_ID

    def seed_predictions(self) -> None:
        """Strategy signals for the Predictions examples, two of them resolved."""
        out = subprocess.run(
            [sys.executable, "-c", SEED_PREDICTIONS], cwd=BACKEND, capture_output=True, text=True
        )
        print(f"   predictions: {(out.stdout or out.stderr).strip()[-200:]}")

    def wait_backtest(self, var: str) -> None:
        for _ in range(60):
            res = self.http.get(
                f"/api/v1/backtests/{self.vars[var]}", headers=self.auth_headers("user")
            )
            if res.json()["status"] not in ("queued", "running"):
                return
            time.sleep(1)
        raise RuntimeError("backtest did not finish: is a Celery worker on queue 'backtests'?")

    # --- setup and the run ---------------------------------------------------------------------
    def setup(self) -> None:
        """A capture user (analyst, so sharing/publishing work) and a public strategy of
        another user, so 'Browse public strategies' has something to show."""
        res = self.http.post(
            "/api/v1/auth/register",
            json={
                "email": CAPTURE_EMAIL,
                "password": CAPTURE_PASSWORD,
                "full_name": "Sara Trader",
            },
        )
        if res.status_code not in (201, 409):
            res.raise_for_status()
        admin = self.auth_headers("admin")
        # Calendar history (the sample CSV the admin import request also sends), so the events
        # list and an event's history have something to show
        self.http.post(
            "/api/v1/admin/calendar/import",
            params={"tz": "America/New_York"},
            files={
                "file": (
                    "sample.csv",
                    (POSTMAN / "samples/calendar_history_sample.csv").read_bytes(),
                    "text/csv",
                )
            },
            headers=admin,
        ).raise_for_status()
        self.seed_ai_setup()
        self.seed_predictions()
        users = self.http.get(
            "/api/v1/admin/users", params={"q": CAPTURE_EMAIL}, headers=admin
        ).json()
        uid = users["items"][0]["id"]
        self.http.patch(f"/api/v1/admin/users/{uid}/role", json={"role": "expert"}, headers=admin)
        self.http.post(
            "/api/v1/auth/register",
            json={
                "email": AUTHOR_EMAIL,
                "password": AUTHOR_PASSWORD,
                "full_name": "Lina Analyst",
            },
        )
        lina = self.http.get(
            "/api/v1/admin/users", params={"q": AUTHOR_EMAIL}, headers=admin
        ).json()["items"][0]["id"]
        self.http.patch(f"/api/v1/admin/users/{lina}/role", json={"role": "analyst"}, headers=admin)
        token = self.http.post(
            "/api/v1/auth/login",
            json={"email": AUTHOR_EMAIL, "password": AUTHOR_PASSWORD},
        ).json()["access_token"]
        lina_auth = {"Authorization": f"Bearer {token}"}
        if not self.http.get("/api/v1/posts", headers=lina_auth).json()["items"]:
            self.http.post(
                "/api/v1/posts",
                headers=lina_auth,
                json={
                    "title": "ETH/BTC: momentum is turning",
                    "body": "Weekly RSI broke its downtrend. I am **long ETH/BTC** while 0.034 "
                    "holds.\n\n> Not financial advice.",
                    "direction": "bullish",
                    "timeframe": "1d",
                },
            ).raise_for_status()
        self.http.post(
            "/api/v1/auth/register",
            json={
                "email": EXPERT_EMAIL,
                "password": EXPERT_PASSWORD,
                "full_name": "Sami Expert",
            },
        )
        sami = self.http.get(
            "/api/v1/admin/users", params={"q": EXPERT_EMAIL}, headers=admin
        ).json()["items"][0]["id"]
        self.http.patch(f"/api/v1/admin/users/{sami}/role", json={"role": "expert"}, headers=admin)
        sami_auth = self.token(EXPERT_EMAIL, EXPERT_PASSWORD)
        self.http.put(
            "/api/v1/me/expert-profile",
            headers=sami_auth,
            json={
                "headline": "Gold & forex macro · 12 years",
                "bio": "Daily XAU/USD and EUR/USD plans with clear invalidation levels.",
                "markets": ["gold", "forex"],
                "languages": ["ar", "en"],
                "response_time_hint": "within a day",
            },
        ).raise_for_status()
        if not self.http.get("/api/v1/me/plans", headers=sami_auth).json():
            self.http.post(
                "/api/v1/me/plans",
                headers=sami_auth,
                json={
                    "name": "Gold desk monthly",
                    "description": "Premium plans, chat and live signals.",
                    "price": "19.00",
                    "interval": "month",
                    "perks": {
                        "premium_posts": True,
                        "chat": True,
                        "signals_feed": True,
                    },
                },
            ).raise_for_status()
            self.http.post(
                "/api/v1/posts",
                headers=sami_auth,
                json={
                    "title": "XAU/USD weekly plan (subscribers)",
                    "body": "Gold holds the 2,380 demand zone. **Plan:** buy dips into 2,385 with "
                    "a stop under 2,362; targets 2,420 and 2,455. Full levels and the scenario "
                    "tree below, plus the invalidation for the bearish case.",
                    "direction": "bullish",
                    "timeframe": "4h",
                    "visibility": "subscribers",
                },
            ).raise_for_status()
        public = self.http.get(
            "/api/v1/custom-strategies/public",
            headers=admin,
            params={"search": "Trend rider"},
        ).json()
        if not public["items"]:
            from spec import EMA_CROSS

            self.http.post(
                "/api/v1/me/custom-strategies",
                headers=admin,
                json={
                    "name": "Trend rider EMA 9/21",
                    "description": "Classic EMA 9/21 crossover, shared by the platform team.",
                    "kind": "builder",
                    "definition": EMA_CROSS,
                    "visibility": "public",
                },
            ).raise_for_status()

    def run_items(self, items: list[Req | Folder]) -> None:
        for item in items:
            if isinstance(item, Folder):
                self.run_items(item.items)
                continue
            self.before(item)
            if item.id == "backtests_compare":
                self.wait_backtest("backtest_id_2")
            if item.id == "backtests_get":
                self.wait_backtest("backtest_id")
            res = self.send(item)
            if res.status_code not in item.expect:
                print(f"!! {item.id}: {res.status_code} {res.text[:300]}")
            else:
                print(f"ok {item.id}: {res.status_code}")
            self.record(item, f"{res.status_code} {res.reason_phrase}", res, None)
            self.after(item, res)
            for variant in item.variants:
                vres = self.send(item, variant)
                flag = "ok" if vres.status_code == variant.status else "!!"
                print(f"{flag}   variant {variant.name!r}: {vres.status_code} {vres.text[:200]}")
                self.record(item, variant.name, vres, variant)
                if item.id == "custom_create" and vres.status_code == 201:
                    self.vars["composite_strategy_id"] = vres.json()["id"]
            if item.id == "apikey_instruments":
                self.rate_limit_example(item)

    def rate_limit_example(self, req: Req) -> None:
        """A real 429: a throwaway key limited to 1 request per minute, called twice."""
        res = self.http.post(
            "/api/v1/me/api-keys",
            headers=self.auth_headers("user"),
            json={
                "name": "rate limit demo",
                "scopes": ["market:read"],
                "rate_limit_per_minute": 1,
            },
        )
        key = res.json()
        saved = self.vars["api_key"]
        self.vars["api_key"] = key["key"]
        self.send(req)
        res = self.send(req)
        self.record(req, "429 Rate limit exceeded", res, Variant("429", 429))
        self.vars["api_key"] = saved
        self.http.delete(f"/api/v1/me/api-keys/{key['id']}", headers=self.auth_headers("user"))
        print(f"ok   variant '429': {res.status_code}")

    def run(self) -> None:
        self.setup()
        self.run_items(FOLDERS)
        OUT.write_text(json.dumps(self.examples, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {sum(len(v) for v in self.examples.values())} examples to {OUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()
    Runner(args.base_url, args.admin_email, args.admin_password).run()


if __name__ == "__main__":
    main()
