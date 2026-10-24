"""B9: the periodic evaluation (app/ai/evaluate.py, app/tasks/ai.py) against the fake
ai-service (tools/fake_ai_service): scheduling and the run key, the request builder (counts,
the cut at the last closed bar, New York trading days across DST, short history, skips), the
answer applied (a whole life cycle, ARMED and ACTIVE at the same time, a backwards state),
what follows the commit (kick, sizes, explanations) and its isolation, an unreachable
ai-service and contract errors, the status block and the request size."""

import gzip
import importlib.util
import json
import logging
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import contract as c
from app.ai import evaluate, sizing
from app.ai.client import AIServiceClient
from app.core.config import get_settings
from app.models.ai import (
    AIAlertFollow,
    AIEvaluationRun,
    AISetup,
    AISetupEvent,
    AISetupSize,
    AISetupTake,
)
from app.models.instrument import Instrument, MarketType
from app.schemas.market import CandleIn
from app.services import market_service
from app.tasks import ai as ai_tasks
from app.tasks import celery_app
from tests.market_utils import make_instrument

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "fake_ai_service", ROOT / "tools" / "fake_ai_service" / "fake_ai_service.py"
)
fake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake)

MIN = timedelta(minutes=1)
M15 = timedelta(minutes=15)
CLOSE = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)  # a Monday; the decision bar is 14:00
GOLD = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
    "quote_currency": "USD",
}
SMALL = {"ai_bars_15m": 20, "ai_bars_1h": 5, "ai_bars_4h": 3, "ai_bars_1d": 2}


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _clean(redis_client: Redis):
    async def clean() -> None:
        keys = [k async for k in redis_client.scan_iter(match="ai:evaluate:*")]
        if keys:
            await redis_client.delete(*keys)

    fake.STATE.reset()
    await clean()
    yield
    await clean()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_evaluate_enabled", True)
    monkeypatch.setattr(s, "ai_evaluate_instruments", "fxpro:XAU/USD")
    monkeypatch.setattr(s, "ai_profiles", "intraday")
    for name, value in SMALL.items():
        monkeypatch.setattr(s, name, value)
    return s


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    # no session calendar: 24/7, so the gate only looks at the data
    return await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity, **GOLD)


def price(ts: datetime) -> float:
    k = (ts - datetime(2026, 1, 1, tzinfo=UTC)) / MIN
    return round(2400 + 3 * math.sin(k / 50), 2)


async def write(
    session: AsyncSession,
    instrument: Instrument,
    start: datetime,
    end: datetime,
    *,
    spread: float | None = 0.25,
    skip: set[datetime] = frozenset(),
) -> None:
    candles = []
    ts = start
    while ts < end:
        if ts not in skip:
            p = price(ts)
            candles.append(
                CandleIn(ts=ts, open=p, high=p + 0.3, low=p - 0.3, close=p + 0.1, volume=1,
                         spread=spread)
            )  # fmt: skip
        ts += MIN
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()


async def history(session, instrument, close: datetime = CLOSE, days: float = 3.0, **kw):
    """1m candles for ``days`` up to ``close`` (the decision bar is the last 15m)."""
    await write(session, instrument, close - timedelta(days=days), close, **kw)


def fake_client() -> AIServiceClient:
    return AIServiceClient("http://fake", transport=httpx.ASGITransport(app=fake.app), backoff=0)


class After:
    """Records kick() and the explain scheduling (no Celery in tests)."""

    def __init__(self) -> None:
        self.kicks = 0
        self.explains: list[tuple[str, str]] = []

    def kick(self) -> None:
        self.kicks += 1

    def explain(self, setup_id: str, lang: str) -> None:
        self.explains.append((setup_id, lang))


@pytest.fixture
def after() -> After:
    return After()


async def run(session_factory, redis_client, after: After, close=CLOSE, **kw):
    return await evaluate.run(
        session_factory,
        redis_client,
        "fxpro",
        "XAU/USD",
        "intraday",
        close,
        now=close + timedelta(seconds=20),
        client=kw.pop("ai", None) or fake_client(),
        kick=after.kick,
        schedule_explain=after.explain,
        **kw,
    )


def evaluate_calls() -> list[dict]:
    return [r for r in fake.STATE.requests if r["path"] == "/v1/evaluate"]


# --- scheduling ----------------------------------------------------------------------------------


def test_tick_schedules_one_run_per_instrument_and_profile(settings, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_evaluate_instruments", "fxpro:XAU/USD, fxpro:eur/usd")
    monkeypatch.setattr(settings, "ai_profiles", "intraday,swing")
    calls = []
    now = CLOSE + timedelta(seconds=1)
    done = evaluate.schedule(now, lambda args, **kw: calls.append((args, kw)))
    assert len(done) == 4
    assert [a for a, _ in calls] == [
        ("fxpro", "XAU/USD", "intraday", "2026-10-19T14:15:00Z"),
        ("fxpro", "XAU/USD", "swing", "2026-10-19T14:15:00Z"),
        ("fxpro", "EUR/USD", "intraday", "2026-10-19T14:15:00Z"),
        ("fxpro", "EUR/USD", "swing", "2026-10-19T14:15:00Z"),
    ]
    assert {kw["eta"] for _, kw in calls} == {CLOSE + timedelta(seconds=20)}


def test_nothing_is_scheduled_when_disabled(monkeypatch) -> None:
    assert get_settings().ai_evaluate_enabled is False  # the shipped default
    calls = []
    assert evaluate.schedule(CLOSE, lambda *a, **kw: calls.append(a)) == []
    assert calls == []
    monkeypatch.setattr(ai_tasks.evaluate, "apply_async", lambda *a, **kw: calls.append(a))
    assert ai_tasks.evaluate_tick() == 0 and calls == []
    assert ai_tasks.evaluate("fxpro", "XAU/USD", "intraday", "2026-10-19T14:15:00Z") == {
        "status": "disabled"
    }


def test_beat_and_routes() -> None:
    entry = celery_app.conf.beat_schedule["ai-evaluate-tick"]
    assert entry["task"] == "ai.evaluate_tick"
    assert celery_app.conf.task_routes["ai.explain"] == {"queue": "notifications"}
    assert "ai.evaluate" not in celery_app.conf.task_routes  # the default queue (worker)


async def test_a_duplicate_task_is_a_no_op(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    await history(session, gold)
    first = await run(session_factory, redis_client, after)
    again = await run(session_factory, redis_client, after)
    assert (first.status, again.status) == ("ok", "duplicate")
    assert len(evaluate_calls()) == 1
    assert await session.scalar(select(func.count()).select_from(AIEvaluationRun)) == 1


# --- the request ---------------------------------------------------------------------------------


async def test_counts_and_the_cut_at_the_last_closed_bar(
    session, gold, settings, monkeypatch
) -> None:
    # 1m data runs 5 minutes into the next bar (the 14:15 bucket is forming in every aggregate)
    await write(session, gold, CLOSE - timedelta(days=3), CLOSE + 5 * MIN)
    built = await evaluate.build_request(session, gold, "intraday", CLOSE, CLOSE + 5 * MIN)
    assert built.skip is None
    req = built.request
    assert {tf: len(b) for tf, b in req.bars.items()} == {"15m": 20, "1h": 5, "4h": 3, "1d": 2}
    assert req.bars["15m"][-1].ts == CLOSE - M15  # the decision bar, not the forming 14:15
    assert req.bars["1h"][-1].ts == datetime(2026, 10, 19, 13, tzinfo=UTC)  # 14:00 is forming
    assert req.bars["4h"][-1].ts == datetime(2026, 10, 19, 8, tzinfo=UTC)  # closed at 12:00
    # Monday 14:15 UTC: the trading day that opened on Sunday 17:00 New York is still open
    assert [b.ts for b in req.bars["1d"]] == [
        datetime(2026, 10, 16, 21, tzinfo=UTC),
        datetime(2026, 10, 17, 21, tzinfo=UTC),
    ]
    assert req.bars["15m"][-1].spread == 0.25 and req.bars["1h"][-1].spread == 0.25
    assert req.bars["1d"][-1].spread is None
    # the decision bar's 1m bars: open of the first, close of the last
    decision = req.bars["15m"][-1]
    assert decision.o == price(CLOSE - M15) and decision.c == price(CLOSE - MIN) + 0.1
    assert req.request_id == "xauusd-intraday-2026-10-19T14:15:00Z"
    assert req.instrument == "XAUUSD" and req.instrument_spec.tick_size == 0.01
    assert built.coverage["15m"] == {
        "requested": 20,
        "sent": 20,
        "from": c.iso_z(CLOSE - 20 * M15),
        "short": False,
    }
    assert built.body_bytes == len(AIServiceClient.encode(req))


@pytest.mark.parametrize(
    ("close", "expected"),
    [
        # March: DST starts on Sunday 8 March. Saturday's day opens 22:00 UTC (EST) and closes
        # 21:00 UTC on Sunday (EDT): 23 hours
        (
            datetime(2026, 3, 10, 14, 15, tzinfo=UTC),
            [("2026-03-07T22:00:00Z", 23), ("2026-03-08T21:00:00Z", 24)],
        ),
        # November: DST ends on Sunday 1 November: that day lasts 25 hours
        (
            datetime(2026, 11, 3, 14, 15, tzinfo=UTC),
            [("2026-10-31T21:00:00Z", 25), ("2026-11-01T22:00:00Z", 24)],
        ),
    ],
)
async def test_daily_bars_follow_new_york_17_00_across_dst(
    session, gold, settings, close, expected
) -> None:
    await history(session, gold, close, days=4)
    now = close + timedelta(seconds=20)
    built = await evaluate.build_request(session, gold, "intraday", close, now)
    days = built.request.bars["1d"]
    hours = [round((c.d1_close(d.ts) - d.ts).total_seconds() / 3600) for d in days]
    assert list(zip([c.iso_z(d.ts) for d in days], hours, strict=True)) == expected
    # OHLC over every 1m bar of the New York day
    for day in days:
        minutes = [day.ts + k * MIN for k in range(int((c.d1_close(day.ts) - day.ts) / MIN))]
        assert day.o == price(minutes[0]) and day.c == price(minutes[-1]) + 0.1
        assert day.h == pytest.approx(max(price(t) for t in minutes) + 0.3)
        assert day.l == pytest.approx(min(price(t) for t in minutes) - 0.3)


async def test_short_history_is_sent_and_reported(
    session, session_factory, redis_client, gold, settings, monkeypatch, after, caplog
) -> None:
    monkeypatch.setattr(settings, "ai_bars_15m", 400)  # 3 days hold 288
    monkeypatch.setattr(settings, "ai_bars_1d", 30)
    await history(session, gold)
    caplog.set_level(logging.WARNING, logger="app.ai.evaluate")
    result = await run(session_factory, redis_client, after)
    assert result.status == "ok"
    assert result.coverage["15m"]["sent"] == 288 and result.coverage["15m"]["short"]
    assert result.coverage["1d"]["short"] and result.coverage["1h"]["short"] is False
    assert "short history" in caplog.text
    row = await session.scalar(select(AIEvaluationRun))
    assert row.coverage["15m"]["sent"] == 288


async def test_no_spread_on_the_decision_bar_is_a_local_abstention(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    await history(session, gold, CLOSE - M15)
    await write(session, gold, CLOSE - M15, CLOSE, spread=None)
    result = await run(session_factory, redis_client, after)
    assert (result.status, result.reason) == ("skipped", "decision_bar_no_spread")
    assert evaluate_calls() == []  # ai-service was not called
    row = await session.scalar(select(AIEvaluationRun))
    assert (row.status, row.reason) == ("skipped", "decision_bar_no_spread")
    # the same shape as an ai-service answer
    resp = c.EvaluateResponse.model_validate(row.detail)
    assert resp.status == c.EvaluateStatus.data_quality_failed
    assert resp.abstentions[0].reason == "decision_bar_no_spread"
    assert resp.request_id == "xauusd-intraday-2026-10-19T14:15:00Z"


async def test_a_degraded_gate_skips_without_a_call(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    holes = {CLOSE - 7 * MIN, CLOSE - 6 * MIN}  # two 1m bars missing in the decision bar
    await history(session, gold, skip=holes)
    result = await run(session_factory, redis_client, after)
    assert (result.status, result.reason) == ("skipped", "data_quality_degraded")
    assert {f["check"] for f in result.detail["abstentions"][0]["detail"]["failed"]} >= {
        "closed_bar"
    }
    assert evaluate_calls() == []


async def test_bars_not_closed_and_missing_decision_bar(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    await history(session, gold, CLOSE - 3 * MIN)  # the feed is 3 minutes behind
    built = await evaluate.build_request(session, gold, "intraday", CLOSE, CLOSE + 20 * MIN)
    assert built.skip.reason == "bars_not_closed"
    assert built.skip.detail == {"watermark": c.iso_z(CLOSE - 3 * MIN)}
    bare = await make_instrument(session, "XAG/USD", "fxpro", MarketType.commodity)
    built = await evaluate.build_request(session, bare, "intraday", CLOSE, CLOSE)
    assert built.skip.reason == "no_specs"


# --- applying the answer -------------------------------------------------------------------------


async def test_a_whole_life_cycle_through_the_fake(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    """DEVELOPING, ARMED, ACTIVE, CLOSED on four bars; open_setups echoes the setup."""
    await history(session, gold, CLOSE + 3 * M15)
    states = []
    for k in range(4):
        result = await run(session_factory, redis_client, after, CLOSE + k * M15)
        assert result.status == "ok", result.detail
        row = await session.scalar(select(AISetup).execution_options(populate_existing=True))
        states.append(row.state)
    assert states == ["DEVELOPING", "ARMED", "ACTIVE", "CLOSED"]
    events = await session.execute(
        select(AISetupEvent.from_state, AISetupEvent.to_state, AISetupEvent.at).order_by(
            AISetupEvent.at, AISetupEvent.id
        )
    )
    assert [(f, t, a) for f, t, a in events.all()] == [
        (None, "DEVELOPING", CLOSE),  # created_at
        ("DEVELOPING", "ARMED", CLOSE + M15),
        ("ARMED", "ACTIVE", CLOSE + 2 * M15),
        ("ACTIVE", "CLOSED", CLOSE + 3 * M15),
    ]
    assert row.realized_r == 2.0
    # the second request echoed the DEVELOPING setup exactly as returned
    assert len(evaluate_calls()) == 4
    assert after.kicks == 4  # every run changed a state
    assert after.explains == [(row.setup_id, "ar"), (row.setup_id, "en")]  # once, on ARMED


async def test_armed_and_active_with_the_same_at(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    fake.STATE.modes["evaluate"] = "same_at"
    await history(session, gold, CLOSE + M15)
    await run(session_factory, redis_client, after)
    result = await run(session_factory, redis_client, after, CLOSE + M15)
    assert [(s.from_state, s.to_state) for s in result.applied.state_changes] == [
        ("DEVELOPING", "ARMED"),
        ("ARMED", "ACTIVE"),
    ]
    assert len({s.at for s in result.applied.state_changes}) == 1
    # ARMED then ACTIVE in one response: sized for the takers of ACTIVE only (it moved on)
    assert result.after["sized"] == {}


async def test_a_backwards_state_is_a_contract_error(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    fake.STATE.modes["evaluate"] = "backwards"
    await history(session, gold, CLOSE + 2 * M15)
    for k in range(3):
        result = await run(session_factory, redis_client, after, CLOSE + k * M15)
    assert result.status == "ok"
    assert result.detail["contract_errors"] == [
        {"setup_id": result.detail["contract_errors"][0]["setup_id"],
         "reason": "sent as DEVELOPING but it is ARMED already"}
    ]  # fmt: skip
    row = await session.scalar(select(AISetup).execution_options(populate_existing=True))
    assert row.state == "ARMED"  # ours is kept
    status = await evaluate.status(session, redis_client)
    assert status["last_contract_error"]["error"] == "state went backwards"


async def test_model_unavailable_is_an_abstention(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    fake.STATE.modes["evaluate"] = "model_unavailable"
    await history(session, gold)
    result = await run(session_factory, redis_client, after)
    assert (result.status, result.reason) == ("abstained", "model_unavailable")
    assert after.kicks == 0
    assert await session.scalar(select(func.count()).select_from(AISetup)) == 0


# --- after the commit ----------------------------------------------------------------------------


async def test_after_commit_kicks_sizes_and_explains(
    session, session_factory, redis_client, gold, settings, after, make_user
) -> None:
    follower = await make_user("follower@example.com")
    taker = await make_user("taker@example.com")
    session.add(AIAlertFollow(user_id=follower.id, instrument_id=gold.id, profile="intraday"))
    await session.commit()
    await history(session, gold, CLOSE + 2 * M15)
    await run(session_factory, redis_client, after)  # DEVELOPING
    armed = await run(session_factory, redis_client, after, CLOSE + M15)  # ARMED
    setup_id = armed.applied.state_changes[0].setup_id
    assert armed.after["kick"] and armed.after["sized"] == {setup_id: 1}
    sized = await session.get(AISetupSize, (setup_id, follower.id))
    assert sized.source == "local"  # the fake has no /v1/size (404): the fallback, with a warning
    assert "ai-service has no /v1/size yet (404); sized by the backend" in sized.warnings
    assert armed.after["explain"] == [f"{setup_id}/ar", f"{setup_id}/en"]
    session.add(AISetupTake(setup_id=setup_id, user_id=taker.id, lots=0.04))
    await session.commit()
    active = await run(session_factory, redis_client, after, CLOSE + 2 * M15)  # ACTIVE
    assert active.after["sized"] == {setup_id: 1}
    assert await session.get(AISetupSize, (setup_id, taker.id)) is not None
    assert active.after["explain"] == []  # only on ARMED


async def test_a_failure_after_the_commit_does_not_fail_the_run(
    session, session_factory, redis_client, gold, settings, monkeypatch, make_user
) -> None:
    def boom(*_a, **_kw):
        raise RuntimeError("down")

    async def boom_async(*_a, **_kw):
        raise RuntimeError("down")

    user = await make_user("follower2@example.com")
    session.add(AIAlertFollow(user_id=user.id, instrument_id=gold.id, profile="intraday"))
    await session.commit()
    monkeypatch.setattr(sizing, "size_setup_for_users", boom_async)
    await history(session, gold, CLOSE + M15)
    for close in (CLOSE, CLOSE + M15):
        result = await evaluate.run(
            session_factory, redis_client, "fxpro", "XAU/USD", "intraday", close,
            now=close + timedelta(seconds=20), client=fake_client(), kick=boom,
            schedule_explain=boom,
        )  # fmt: skip
        assert result.status == "ok"
    assert len(result.after["errors"]) == 4  # kick, size, explain ar, explain en
    row = await session.scalar(select(AISetup).execution_options(populate_existing=True))
    assert row.state == "ARMED"  # the evaluation itself is stored


# --- ai-service unreachable and contract errors --------------------------------------------------


async def test_404_and_refused_are_unavailable_logged_once_an_hour(
    session, session_factory, redis_client, gold, settings, after, caplog
) -> None:
    await history(session, gold, CLOSE + M15)
    caplog.set_level(logging.DEBUG, logger="app.ai.evaluate")
    fake.STATE.modes["evaluate"] = "404"
    first = await run(session_factory, redis_client, after)

    class Refused(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("refused", request=request)

    refused = AIServiceClient("http://down", transport=Refused(), backoff=0)
    second = await run(session_factory, redis_client, after, CLOSE + M15, ai=refused)
    assert (first.status, first.reason) == ("unavailable", "no_evaluate_endpoint")
    assert (second.status, second.reason) == ("unavailable", "connection_refused")
    warnings = [
        r for r in caplog.records if r.name == "app.ai.evaluate" and r.levelno >= logging.WARNING
    ]
    assert len(warnings) == 1 and "at most once an hour" in warnings[0].getMessage()
    status = await evaluate.status(session, redis_client)
    [last] = status["last_runs"]
    assert (last["status"], last["reason"]) == ("unavailable", "connection_refused")
    assert status["runs_last_24h"] == {"unavailable": 2}


async def test_422_is_a_contract_error_and_flagged(
    session, session_factory, redis_client, gold, settings, after, client, admin_headers
) -> None:
    await history(session, gold)
    fake.STATE.modes["evaluate"] = "422"
    result = await run(session_factory, redis_client, after)
    assert (result.status, result.reason) == ("contract_error", "http_422")
    assert len(evaluate_calls()) == 1  # never retried
    res = await client.get("/api/v1/admin/system/status", headers=admin_headers)
    block = res.json()["ai_evaluate"]
    assert block["enabled"] is True and block["profiles"] == ["intraday"]
    assert block["last_runs"][0]["status"] == "contract_error"
    assert block["last_contract_error"]["request_id"] == "xauusd-intraday-2026-10-19T14:15:00Z"


async def test_503_is_retried_then_unavailable(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    await history(session, gold)
    fake.STATE.modes["evaluate"] = "503"
    result = await run(session_factory, redis_client, after)
    assert result.status == "unavailable" and result.reason == "503"
    assert len(evaluate_calls()) == get_settings().ai_max_retries + 1


async def test_gzip_request_bodies(
    session, session_factory, redis_client, gold, settings, after, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ai_request_gzip", True)
    await history(session, gold)
    result = await run(session_factory, redis_client, after)
    assert result.status == "ok"
    [call] = evaluate_calls()
    assert call["gzip"] and call["bytes"] == result.request_bytes  # decompressed size


# --- size of a full request ----------------------------------------------------------------------


def test_request_size_with_the_default_counts() -> None:
    """2,000 x 15m + 500 x 1h + 300 x 4h + 260 x 1d (the defaults), 10 open setups and 20
    calendar events: the body ai-service gets, plain and gzip (docs/ai-contract.md)."""
    s = get_settings()
    assert (s.ai_bars_15m, s.ai_bars_1h, s.ai_bars_4h, s.ai_bars_1d) == (2000, 500, 300, 260)
    base = c.EvaluateRequest.model_validate(json.loads(
        (ROOT / "docs/api/ai-service-examples/evaluate-request.json").read_text("utf-8")
    ))  # fmt: skip

    def bars(tf: str, n: int, last: datetime) -> list[dict]:
        out, ts = [], last
        for _ in range(n):
            p = 2400 + (ts.timestamp() % 997) / 100
            out.append(
                {
                    "ts": c.iso_z(ts),
                    "o": round(p, 2),
                    "h": round(p + 1.37, 2),
                    "l": round(p - 1.21, 2),
                    "c": round(p + 0.42, 2),
                    "spread": 0.2533,
                }
            )
            ts = c.d1_open(ts - timedelta(hours=1)) if tf == "1d" else ts - c.TIMEFRAMES[tf]
        return out[::-1]  # fmt: skip

    close = base.bar_close_ts
    req = c.EvaluateRequest.model_validate(
        {
            **base.model_dump(mode="json"),
            "bars": {
                "15m": bars("15m", 2000, close - M15),
                "1h": bars("1h", 500, datetime(2026, 10, 19, 13, tzinfo=UTC)),
                "4h": bars("4h", 300, datetime(2026, 10, 19, 8, tzinfo=UTC)),
                "1d": bars("1d", 260, datetime(2026, 10, 15, 21, tzinfo=UTC)),
            },
            "open_setups": [
                {**base.open_setups[0].payload(), "setup_id": f"s{k}"} for k in range(10)
            ],
            "calendar": base.model_dump(mode="json")["calendar"] * 10,
        }
    )
    body = AIServiceClient.encode(req)
    packed = gzip.compress(body, mtime=0)
    print(f"evaluate request: {len(body)} bytes, gzip {len(packed)} bytes")  # noqa: T201
    assert 250_000 < len(body) < 450_000  # ~3,060 bars at ~100 bytes
    assert len(packed) < len(body) / 3


async def test_old_runs_are_cleaned_up(
    session, session_factory, redis_client, gold, settings, after
) -> None:
    from app.services import housekeeping  # noqa: PLC0415

    await history(session, gold)
    await run(session_factory, redis_client, after)
    now = datetime.now(UTC)
    assert (await housekeeping.cleanup(session, now)).ai_evaluation_runs == 0
    assert (await housekeeping.cleanup(session, now + timedelta(days=91))).ai_evaluation_runs == 1


async def test_a_failure_while_applying_is_recorded(
    session, session_factory, redis_client, gold, settings, after, monkeypatch
) -> None:
    async def broken(*_a, **_kw):
        raise RuntimeError("database gone")

    monkeypatch.setattr(evaluate.store, "apply_evaluation", broken)
    await history(session, gold)
    result = await run(session_factory, redis_client, after)
    assert (result.status, result.reason) == ("error", "apply_failed")
    row = await session.scalar(select(AIEvaluationRun))
    assert row.status == "error" and "database gone" in row.detail["error"]
