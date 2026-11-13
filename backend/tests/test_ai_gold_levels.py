"""B13 (contract 0.3.0): the gold_levels profile and the daily volatility.

- the contract: ``exit_type`` (a target needs ``tp``; trailing and time take a null ``tp`` and
  ``r_multiple``; the stop on the right side), the setup ids, ``sl_moved``, ``volatility``;
- the store: ``sl_moved`` updates ``sl`` and keeps every move, an invalid one is a warning,
  ``exit_reason`` from the setup or its CLOSED transition, the outbox;
- the schedule per profile (5m boundaries: gold_levels; 15m: both) and the 5m spreads;
- the whole life cycle through the fake ai-service in ``gold_levels`` mode;
- volatility: stored once per day, every other status, an unknown level, a malformed block, the
  ``today`` and history endpoints, ``/admin/system/status``;
- alerts: the exit rule in the ARMED text, ``sl_moved`` to takers only (and off with
  ``AI_NOTIFY_SL_MOVED``), quiet hours, no alert when a setup without a target expires;
- Y16 without a target (``realized_r`` decides, ``risk_reward`` null), the API exposure.
"""

import json
import logging
import math
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import alerts, evaluate, labels, store, volatility
from app.ai import contract as c
from app.ai.client import AIServiceClient
from app.core.config import get_settings
from app.models.ai import (
    AIAlertFollow,
    AISetup,
    AISetupEvent,
    AISetupOutbox,
    AISetupTake,
    AIVolatilityDaily,
)
from app.models.instrument import Instrument, MarketType
from app.models.notification import Notification, NotificationDelivery, NotificationType
from app.notifications import preferences as prefs_mod
from app.notifications import templates
from app.schemas.market import CandleIn
from app.services import market_service
from tests.market_utils import make_instrument
from tests.test_ai_alerts import FakeAI, user_with_targets
from tests.test_ai_evaluate import GOLD, SMALL, After, fake, write
from tests.test_ai_store import VERSIONS, load
from tests.utils import bearer

MIN = timedelta(minutes=1)
M5 = timedelta(minutes=5)
M15 = timedelta(minutes=15)
CLOSE = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)  # Monday 10:15 New York (EDT)
GL = "gold_levels"
SETUP_ID = "xauusd-gold_levels-lvl4h-pdh-20261019"
GL_BARS = "5m:24,1h:5,4h:3,1d:2"


# --- fixtures and helpers ------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _clean(redis_client):
    async def clean() -> None:
        keys = [k async for k in redis_client.scan_iter(match="ai:*")]
        if keys:
            await redis_client.delete(*keys)

    fake.STATE.reset()
    await clean()
    yield
    await clean()
    fake.STATE.reset()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_evaluate_enabled", True)
    monkeypatch.setattr(s, "ai_evaluate_instruments", "fxpro:XAU/USD")
    monkeypatch.setattr(s, "ai_profiles", "intraday,gold_levels")
    monkeypatch.setattr(s, "ai_gold_levels_instruments", "fxpro:XAU/USD")
    monkeypatch.setattr(s, "ai_gold_levels_bars", GL_BARS)
    for name, value in SMALL.items():
        monkeypatch.setattr(s, name, value)
    return s


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    return await make_instrument(
        session, "XAU/USD", "fxpro", MarketType.commodity, price_precision=2, **GOLD
    )


def fake_client() -> AIServiceClient:
    return AIServiceClient("http://fake", transport=httpx.ASGITransport(app=fake.app), backoff=0)


async def run(session_factory, redis_client, close: datetime, profile: str = GL, after=None):
    after = after or After()
    return await evaluate.run(
        session_factory, redis_client, "fxpro", "XAU/USD", profile, close,
        now=close + timedelta(seconds=20), client=fake_client(), kick=after.kick,
        schedule_explain=after.explain,
    )  # fmt: skip


def gl_setup(state: str = "ARMED", **changes) -> dict:
    return {
        "setup_id": SETUP_ID,
        "state": state,
        "direction": "buy",
        "entry": 4100.0,
        "sl": 4090.0,
        "tp": None,
        "r_multiple": None,
        "probability": None,
        "ev_r": None,
        "ev_r_lower": None,
        "grade": None,
        "exit_type": "trailing",
        "evidence": {"level": "pdh"},
        "features": {},
        **changes,
    }


def gl_request(close: datetime) -> c.EvaluateRequest:
    base = load("evaluate-request")
    bar = {"ts": c.iso_z(close - M5), "o": 4100, "h": 4101, "l": 4099, "c": 4100, "spread": 0.25}
    return c.EvaluateRequest.model_validate(
        {
            **base,
            "request_id": c.make_request_id("XAUUSD", GL, close),
            "profile": GL,
            "bar_close_ts": c.iso_z(close),
            "bars": {"5m": [bar]},
            "open_setups": [],
        }
    )


def gl_response(req, *, new=(), transitions=(), **extra) -> c.EvaluateResponse:
    return c.EvaluateResponse.model_validate(
        {
            "request_id": req.request_id,
            "status": "ok",
            "versions": VERSIONS,
            "new_setups": list(new),
            "transitions": list(transitions),
            "abstentions": [],
            **extra,
        }
    )


def move(frm: str, to: str, at: datetime, setup_id: str = SETUP_ID, **extra) -> dict:
    return {"setup_id": setup_id, "from": frm, "to": to, "at": c.iso_z(at), **extra}


async def apply(session, gold, close, *, new=(), transitions=()) -> store.ApplyResult:
    req = gl_request(close)
    resp = gl_response(req, new=new, transitions=transitions)
    return await store.apply_evaluation(session, gold, req, resp)


T = [CLOSE + k * M5 for k in range(6)]
HISTORY = [move("DEVELOPING", "ARMED", T[0]), move("ARMED", "ACTIVE", T[1])]


async def armed_then_active(session, gold) -> None:
    await apply(session, gold, T[0], new=[gl_setup("ARMED")])
    await apply(session, gold, T[1], new=[gl_setup("ACTIVE")], transitions=HISTORY[1:])


async def events(session, setup_id: str = SETUP_ID) -> list[tuple]:
    rows = await session.execute(
        select(AISetupEvent.from_state, AISetupEvent.to_state, AISetupEvent.reason, AISetupEvent.sl)
        .where(AISetupEvent.setup_id == setup_id)
        .order_by(AISetupEvent.at, AISetupEvent.id)
    )
    return [tuple(r) for r in rows.all()]


async def fresh(session, setup_id: str = SETUP_ID) -> AISetup:
    return await session.get(AISetup, setup_id, populate_existing=True)


# --- the contract --------------------------------------------------------------------------------


@pytest.mark.parametrize("exit_type", ["trailing", "time"])
def test_no_target_takes_a_null_tp_and_r_multiple(exit_type: str) -> None:
    for state in ("ARMED", "ACTIVE"):
        setup = c.Setup.model_validate(gl_setup(state, exit_type=exit_type))
        assert setup.tp is None and setup.r_multiple is None
        assert setup.exit_type == exit_type
    sell = gl_setup(direction="sell", sl=4110.0, exit_type=exit_type)
    assert c.Setup.model_validate(sell).direction == "sell"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"tp": 4120.0}, "exit_type trailing: tp and r_multiple must be null"),
        ({"r_multiple": 1.5}, "exit_type trailing: tp and r_multiple must be null"),
        ({"sl": None}, "a ARMED setup needs entry and sl"),
        ({"sl": 4105.0}, "buy: sl < entry"),
        ({"sl": 4100.0}, "buy: sl < entry"),
        ({"direction": "sell"}, "sell: sl > entry"),
        ({"exit_type": "target"}, "needs entry, sl and tp"),
        ({"exit_type": None}, "needs entry, sl and tp"),
        ({"exit_type": "breakeven"}, "'target', 'trailing' or 'time'"),
        ({"exit_type": "time", "sl": 4101.0}, "buy: sl < entry"),
    ],
)
def test_exit_type_rules(changes: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        c.Setup.model_validate(gl_setup(**changes))


def test_a_target_still_needs_tp_and_echo_is_exact() -> None:
    target = {**gl_setup(), "exit_type": "target", "tp": 4120.0, "r_multiple": 2.0}
    assert c.Setup.model_validate(target).tp == 4120.0
    for state in ("DEVELOPING", "CLOSED", "EXPIRED", "INVALIDATED"):  # no prices needed
        c.Setup.model_validate(gl_setup(state, entry=None, sl=None))
    raw = {**gl_setup(), "exit_reason": None, "levels": {"pdh": 4100.0}}
    assert c.Setup.model_validate(raw).payload() == raw  # echoed exactly in open_setups


def test_gold_levels_setup_ids_are_accepted() -> None:
    for setup_id in (
        "xauusd-gold_levels-lvl4h-pdh-20261113",
        "xauusd-gold_levels-round-r4100-20261113",
        "xauusd-gold_levels-lvl1h-asia_high-20261113",
    ):
        assert c.Setup.model_validate(gl_setup(setup_id=setup_id)).setup_id == setup_id


def test_sl_moved_transition_and_exit_reason() -> None:
    raw = {"setup_id": SETUP_ID, "from": "ACTIVE", "to": "ACTIVE", "at": "2026-11-13T15:40:00Z",
           "reason": "sl_moved", "sl": 4092.15}  # fmt: skip
    t = c.Transition.model_validate(raw)
    assert (t.from_, t.to, t.sl, t.reason) == ("ACTIVE", "ACTIVE", 4092.15, c.SL_MOVED)
    closed = c.Transition.model_validate(
        {**raw, "to": "CLOSED", "reason": "trailing_stop", "exit_reason": "trailing_stop",
         "realized_r": 1.4, "sl": None}
    )  # fmt: skip
    assert closed.exit_reason == "trailing_stop" and closed.realized_r == 1.4
    with pytest.raises(ValidationError):
        c.Transition.model_validate({**raw, "sl": 0})


VOL_OK = {
    "status": "ok",
    "model": "vol-1",
    "day": "2026-10-19",
    "window": "02:00-16:45 America/New_York",
    "expected_move_pct": 1.1,
    "range_pct": {"p20": 0.6, "p50": 0.9, "p80": 1.4},
    "range_usd": {"p20": 24.6, "p50": 36.9, "p80": 57.4},
    "level": "normal",
    "news": [{"ts": "2026-10-19T12:30:00Z", "title": "CPI m/m", "top3": True}],
}


def test_volatility_is_optional_and_lenient() -> None:
    base = load("evaluate-response-ok")
    assert c.EvaluateResponse.model_validate(base).volatility is None  # older answers
    ok = c.EvaluateResponse.model_validate({**base, "volatility": VOL_OK}).volatility
    assert ok.status == "ok" and ok.range_pct.p80 == 1.4 and ok.warnings() == []
    for status in ("outside_window", "insufficient_history", "not_supported"):
        empty = {"status": status, "day": "2026-10-19", "expected_move_pct": None,
                 "range_pct": {"p20": None, "p50": None, "p80": None}, "level": None}  # fmt: skip
        vol = c.EvaluateResponse.model_validate({**base, "volatility": empty}).volatility
        assert vol.status == status and vol.expected_move_pct is None and vol.warnings() == []
    odd = {**VOL_OK, "status": "warming_up", "level": "extreme"}
    vol = c.EvaluateResponse.model_validate({**base, "volatility": odd}).volatility
    assert (vol.status, vol.level) == ("warming_up", "extreme")  # kept as received
    assert vol.warnings() == [
        "unknown volatility status 'warming_up'",
        "unknown volatility level 'extreme'",
    ]
    bad = c.EvaluateResponse.model_validate(
        {**base, "volatility": {**VOL_OK, "expected_move_pct": "a lot"}}
    )
    assert bad.volatility is None and "expected_move_pct" in bad.volatility_error
    assert len(bad.new_setups) == 2  # the rest of the response stands


# --- the store: exit_type, sl_moved --------------------------------------------------------------


async def test_a_setup_without_target_is_stored(session: AsyncSession, gold) -> None:
    result = await apply(session, gold, T[0], new=[gl_setup("ARMED")])
    assert result.inserted == 1
    row = await fresh(session)
    assert (row.profile, row.exit_type, row.tp, row.r_multiple) == (GL, "trailing", None, None)
    assert row.exit_reason is None and row.last_payload["exit_type"] == "trailing"


async def test_sl_moved_updates_sl_and_keeps_every_move(session: AsyncSession, gold) -> None:
    await armed_then_active(session, gold)
    first = move("ACTIVE", "ACTIVE", T[2], reason="sl_moved", sl=4093.0)
    second = move("ACTIVE", "ACTIVE", T[3], reason="sl_moved", sl=4096.5)
    r2 = await apply(session, gold, T[2], new=[gl_setup("ACTIVE", sl=4093.0)],
                     transitions=[*HISTORY, first])  # fmt: skip
    r3 = await apply(session, gold, T[3], new=[gl_setup("ACTIVE", sl=4096.5)],
                     transitions=[*HISTORY, first, second])  # fmt: skip
    assert (r2.sl_moves, r3.sl_moves) == (1, 1) and r3.transitions_known == 3
    assert [(s.from_state, s.to_state, s.reason, s.sl) for s in r3.state_changes] == [
        ("ACTIVE", "ACTIVE", "sl_moved", 4096.5)
    ]
    row = await fresh(session)
    assert row.sl == 4096.5 and row.state == "ACTIVE"
    assert await events(session) == [
        (None, "ARMED", None, None),
        ("ARMED", "ACTIVE", None, None),
        ("ACTIVE", "ACTIVE", "sl_moved", 4093.0),
        ("ACTIVE", "ACTIVE", "sl_moved", 4096.5),
    ]
    again = await apply(session, gold, T[3], new=[gl_setup("ACTIVE", sl=4096.5)],
                        transitions=[*HISTORY, first, second])  # fmt: skip
    assert again.state_changes == [] and again.sl_moves == 0  # a replay adds nothing
    # one outbox row per move, never a second ACTIVE alert
    rows = (await session.scalars(select(AISetupOutbox).order_by(AISetupOutbox.id))).all()
    assert [(o.to_state, o.reason, o.sl) for o in rows] == [
        ("ARMED", "new", None),
        ("ACTIVE", None, None),
        ("ACTIVE", "sl_moved", 4093.0),
        ("ACTIVE", "sl_moved", 4096.5),
    ]
    # the CLOSED transition carries exit_reason; the moves before it stay history
    closed = move("ACTIVE", "CLOSED", T[4], reason="trailing_stop", realized_r=1.6,
                  exit_reason="trailing_stop")  # fmt: skip
    r4 = await apply(session, gold, T[4], new=[gl_setup("CLOSED", sl=4096.5)],
                     transitions=[*HISTORY, first, second, closed])  # fmt: skip
    row = await fresh(session)
    assert (row.state, row.exit_reason, row.realized_r) == ("CLOSED", "trailing_stop", 1.6)
    assert r4.transitions_known == 4 and r4.warnings == []


async def test_an_invalid_sl_moved_is_a_warning(session: AsyncSession, gold, caplog) -> None:
    await armed_then_active(session, gold)
    caplog.set_level(logging.WARNING, logger="app.ai.store")
    bad = [
        move("ACTIVE", "ACTIVE", T[2], reason="sl_moved", sl=4105.0),  # above a buy's entry
        move("ACTIVE", "ACTIVE", T[2] + MIN, reason="sl_moved"),  # no sl
        move("ACTIVE", "ARMED", T[2] + 2 * MIN, reason="sl_moved", sl=4095.0),  # two states
    ]
    good = move("ACTIVE", "ACTIVE", T[2] + 3 * MIN, reason="sl_moved", sl=4094.0)
    result = await apply(session, gold, T[2], new=[gl_setup("ACTIVE", sl=4094.0)],
                         transitions=[*HISTORY, *bad, good])  # fmt: skip
    assert [w.reason for w in result.warnings] == [
        "sl_moved: sl 4105.0 on the wrong side of entry 4100.0 (buy)",
        "sl_moved without sl",
        "sl_moved from ACTIVE to ARMED",
    ]
    assert result.contract_errors == [] and result.rejected == []
    assert result.sl_moves == 1 and (await fresh(session)).sl == 4094.0
    assert "contract warning" in caplog.text
    # a stop move in a state the setup is not in yet: a warning too
    await apply(session, gold, T[0], new=[gl_setup("ARMED", setup_id="other-1")])
    early = await apply(
        session, gold, T[3],
        transitions=[move("ACTIVE", "ACTIVE", T[3], setup_id="other-1", reason="sl_moved",
                          sl=4095.0)],
    )  # fmt: skip
    assert [w.reason for w in early.warnings] == ["sl_moved in ACTIVE but the setup is ARMED"]


async def test_exit_reason_on_the_setup_and_the_outbox_setting(
    session: AsyncSession, gold, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_notify_sl_moved", False)
    await armed_then_active(session, gold)
    moved = move("ACTIVE", "ACTIVE", T[2], reason="sl_moved", sl=4095.0)
    result = await apply(session, gold, T[2], new=[gl_setup("ACTIVE", sl=4095.0)],
                         transitions=[*HISTORY, moved])  # fmt: skip
    assert result.sl_moves == 1
    assert await session.scalar(
        select(func.count()).select_from(AISetupOutbox).where(AISetupOutbox.sl.is_not(None))
    ) == 0  # AI_NOTIFY_SL_MOVED off: nothing to send  # fmt: skip
    closed = move("ACTIVE", "CLOSED", T[3], reason="time", realized_r=-0.3)
    await apply(session, gold, T[3], new=[gl_setup("CLOSED", exit_reason="time")],
                transitions=[*HISTORY, moved, closed])  # fmt: skip
    row = await fresh(session)
    assert (row.exit_reason, row.realized_r) == ("time", -0.3)  # from the setup


# --- the schedule per profile --------------------------------------------------------------------


def test_5m_boundaries_schedule_gold_levels_and_15m_both(settings, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_evaluate_instruments", "fxpro:XAU/USD,fxpro:EUR/USD")
    calls = []

    def tick(at: datetime) -> list[tuple]:
        calls.clear()
        evaluate.schedule(at + timedelta(seconds=1), lambda a, **kw: calls.append((a, kw)))
        return [a[:3] for a, _ in calls]

    assert tick(CLOSE - 10 * MIN) == [("fxpro", "XAU/USD", GL)]  # 14:05
    assert calls[0][0][3] == "2026-10-19T14:05:00Z"
    eta = CLOSE - 10 * MIN + timedelta(seconds=20)
    assert calls[0][1] == {"eta": eta, "expires": eta + M5 - timedelta(seconds=120)}
    assert tick(CLOSE) == [
        ("fxpro", "XAU/USD", "intraday"),
        ("fxpro", "XAU/USD", GL),
        ("fxpro", "EUR/USD", "intraday"),  # gold_levels runs on its own instruments only
    ]
    intraday = calls[0][1]
    assert intraday["expires"] == intraday["eta"] + M15 - timedelta(seconds=120)
    assert {a[3] for a, _ in calls} == {"2026-10-19T14:15:00Z"}
    # a tick a little late still schedules its own boundary
    assert tick(CLOSE + 5 * MIN + timedelta(seconds=40)) == [("fxpro", "XAU/USD", GL)]
    # off until gold_levels is in AI_PROFILES (the shipped default is intraday)
    monkeypatch.setattr(settings, "ai_profiles", "intraday")
    assert tick(CLOSE - 10 * MIN) == []
    assert type(get_settings()).model_fields["ai_profiles"].default == "intraday"


def test_profile_settings() -> None:
    s = get_settings()
    assert s.ai_gold_levels_bars == "5m:3000,1h:500,4h:300,1d:260"  # the shipped defaults
    assert s.ai_profile_bar_counts(GL) == {"5m": 3000, "1h": 500, "4h": 300, "1d": 260}
    assert s.ai_profile_bar_counts("intraday") == s.ai_bar_counts
    assert s.ai_profile_instrument_list(GL) == [("fxpro", "XAU/USD")]
    assert s.ai_notify_sl_moved is True
    assert evaluate.decision_timeframe(GL) == "5m"
    assert evaluate.decision_timeframe("intraday") == "15m"
    from app.core.config import _counts  # noqa: PLC0415

    assert _counts("1h:5, 5m:24,bad,2w:3,4h:x,1d:0") == {"5m": 24, "1h": 5}


def spread_at(ts: datetime) -> float:
    return round(0.20 + 0.01 * (ts.minute % 15), 4)


async def write_spreads(session, instrument, start: datetime, end: datetime) -> None:
    candles, ts = [], start
    while ts < end:
        p = round(4100 + 3 * math.sin(ts.timestamp() / 3000), 2)
        candles.append(CandleIn(ts=ts, open=p, high=p + 0.3, low=p - 0.3, close=p + 0.1,
                                volume=1, spread=spread_at(ts)))  # fmt: skip
        ts += MIN
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()


async def test_5m_spread_aggregation(session, gold, settings) -> None:
    await write_spreads(session, gold, CLOSE - timedelta(days=3), CLOSE + 2 * MIN)
    buckets = await evaluate._spreads(session, gold, CLOSE - M15, CLOSE, M5)
    assert {b: round(t / n, 4) for b, (t, n) in buckets.items()} == {
        CLOSE - M15: 0.22,  # minutes 0-4 of the quarter
        CLOSE - 2 * M5: 0.27,
        CLOSE - M5: 0.32,
    }
    built = await evaluate.build_request(session, gold, GL, CLOSE, CLOSE + 2 * MIN)
    assert built.skip is None, built.skip
    req = built.request
    assert req.request_id == "xauusd-gold_levels-2026-10-19T14:15:00Z"
    assert {tf: len(b) for tf, b in req.bars.items()} == {"5m": 24, "1h": 5, "4h": 3, "1d": 2}
    assert req.bars["5m"][-1].ts == CLOSE - M5  # the decision bar
    assert [b.spread for b in req.bars["5m"][-3:]] == [0.22, 0.27, 0.32]
    assert req.bars["1h"][-1].spread == pytest.approx(0.27)  # 0.20 + 0.01 x mean(0..14)
    assert built.coverage["5m"] == {"requested": 24, "sent": 24,
                                    "from": c.iso_z(CLOSE - 24 * M5), "short": False}  # fmt: skip
    # a 5m boundary that is not a 15m one is a decision bar too
    off_quarter = await evaluate.build_request(session, gold, GL, CLOSE - M5, CLOSE + 2 * MIN)
    assert off_quarter.skip is None and off_quarter.request.bars["5m"][-1].spread == 0.27
    # and intraday is not affected: its 15m buckets
    intraday = await evaluate.build_request(session, gold, "intraday", CLOSE, CLOSE + 2 * MIN)
    assert intraday.request.bars["15m"][-1].spread == pytest.approx(0.27)


# --- the whole life cycle through the fake -------------------------------------------------------


async def gl_lifecycle(session, session_factory, redis_client, gold) -> list:
    fake.STATE.modes["evaluate"] = "gold_levels"
    await write(session, gold, CLOSE - timedelta(days=3), CLOSE + 5 * M5)
    results = []
    after = After()
    for k in range(5):
        result = await run(session_factory, redis_client, CLOSE + k * M5, after=after)
        assert result.status == "ok", result.detail
        results.append(result)
    return results


async def test_the_gold_levels_life_cycle(
    session, session_factory, redis_client, gold, settings
) -> None:
    results = await gl_lifecycle(session, session_factory, redis_client, gold)
    setups = {
        s.setup_id: s
        for s in (await session.scalars(select(AISetup).execution_options(populate_existing=True)))
    }
    a, b, cc = (
        "xauusd-gold_levels-lvl4h-pdh-20261019",
        "xauusd-gold_levels-lvl4h-pdl-20261019",
        f"xauusd-gold_levels-round-r{int(setups[SETUP_ID].entry)}-20261019",
    )
    assert set(setups) == {a, b, cc}
    assert (setups[a].state, setups[a].exit_reason, setups[a].realized_r) == (
        "CLOSED", "trailing_stop", 1.6)  # fmt: skip
    assert (setups[a].exit_type, setups[a].tp, setups[a].r_multiple) == ("trailing", None, None)
    assert setups[b].state == "EXPIRED" and setups[cc].state == "INVALIDATED"
    moves = [(f, t, r) for f, t, r, sl in await events(session, a)]
    assert moves == [
        (None, "DEVELOPING", None),  # where its history starts, at created_at
        ("DEVELOPING", "ARMED", "level_armed"),
        ("ARMED", "ACTIVE", "entry_filled"),
        ("ACTIVE", "ACTIVE", "sl_moved"),
        ("ACTIVE", "ACTIVE", "sl_moved"),
        ("ACTIVE", "CLOSED", "trailing_stop"),
    ]
    stops = [sl for *_, sl in await events(session, a) if sl is not None]
    assert stops == sorted(stops) and len(stops) == 2 and setups[a].sl == stops[-1]
    assert [r.detail.get("sl_moves", 0) for r in results] == [0, 0, 1, 1, 0]
    assert not any("contract_warnings" in r.detail for r in results)
    reason = await session.scalar(
        select(AISetupEvent.reason).where(
            AISetupEvent.setup_id == cc, AISetupEvent.to_state == "INVALIDATED"
        )
    )
    assert reason == "strategy_busy"
    # the requests: 5m decision bars, the gold_levels profile, open setups echoed
    received = [r for r in fake.STATE.requests if r["path"] == "/v1/evaluate"]
    assert [r["request_id"] for r in received] == [
        f"xauusd-gold_levels-{c.iso_z(CLOSE + k * M5)}" for k in range(5)
    ]


# --- volatility ----------------------------------------------------------------------------------


async def test_volatility_is_stored_once_per_day(
    session, session_factory, redis_client, gold, settings, client, admin_headers
) -> None:
    await write(session, gold, CLOSE - timedelta(days=3), CLOSE + 2 * M15)
    first = await run(session_factory, redis_client, CLOSE, "intraday")
    assert first.detail["volatility"] == {"status": "ok", "day": "2026-10-19", "stored": True}
    second = await run(session_factory, redis_client, CLOSE + M15, "intraday")
    assert second.detail["volatility"]["stored"] is False  # the first ok of the day stays
    [row] = (await session.scalars(select(AIVolatilityDaily))).all()
    assert (row.day.isoformat(), row.status, row.level, row.model) == (
        "2026-10-19", "ok", "normal", "fake-vol-1")  # fmt: skip
    assert row.range_pct == {"p20": 0.6, "p50": 0.9, "p80": 1.4}
    assert row.request_id == "xauusd-intraday-2026-10-19T14:15:00Z"
    # a later ok with other numbers changes nothing
    other = c.Volatility.model_validate({**VOL_OK, "expected_move_pct": 9.9, "level": "quiet"})
    assert await store.store_volatility(session, gold, "later", other) is False
    await session.refresh(row)
    assert (row.expected_move_pct, row.level) == (1.1, "normal")
    block = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    vol = block["ai_evaluate"]["volatility"]
    assert vol["last_stored_day"]["day"] == "2026-10-19"
    assert vol["last_stored_day"]["instrument"] == "fxpro:XAU/USD"
    assert vol["last_received"]["status"] == "ok" and vol["last_received"]["stored"] is False
    profiles = block["ai_evaluate"]["profile_settings"]
    assert profiles[GL] == {"timeframe": "5m", "instruments": ["fxpro:XAU/USD"],
                            "bars": {"5m": 24, "1h": 5, "4h": 3, "1d": 2}}  # fmt: skip
    assert profiles["intraday"]["timeframe"] == "15m"


@pytest.mark.parametrize(
    "mode",
    ["outside_window", "insufficient_history", "not_supported", "unknown_level", "malformed"],
)
async def test_volatility_statuses(
    session, session_factory, redis_client, gold, settings, mode, caplog
) -> None:
    fake.STATE.modes["volatility"] = mode
    caplog.set_level(logging.WARNING, logger="app.ai.evaluate")
    await write(session, gold, CLOSE - timedelta(days=3), CLOSE)
    result = await run(session_factory, redis_client, CLOSE, "intraday")
    assert result.status == "ok"  # never fails the response
    stored = (await session.scalars(select(AIVolatilityDaily))).all()
    last = await evaluate.status(session, redis_client)
    if mode == "unknown_level":
        assert [r.level for r in stored] == ["extreme"]  # stored as received
        assert "unknown volatility level 'extreme'" in caplog.text
    elif mode == "malformed":
        assert stored == [] and "malformed volatility dropped" in caplog.text
        assert result.detail["volatility"]["status"] is None
        assert last["volatility"]["last_received"] is None
    else:
        assert stored == []
        assert result.detail["volatility"] == {"status": mode, "day": "2026-10-19",
                                               "stored": False}  # fmt: skip
        assert last["volatility"]["last_received"]["status"] == mode


@pytest.mark.parametrize(
    ("now", "reason"),
    [
        (datetime(2026, 10, 19, 5, 30, tzinfo=UTC), "before_window"),  # Monday 01:30 New York
        (datetime(2026, 10, 19, 6, 0, tzinfo=UTC), "not_received"),  # 02:00
        (datetime(2026, 10, 19, 20, 50, tzinfo=UTC), "not_received"),  # 16:50
        (datetime(2026, 10, 19, 21, 30, tzinfo=UTC), "before_window"),  # 17:30: Tuesday's day
        (datetime(2026, 10, 17, 15, 0, tzinfo=UTC), "weekend"),  # Saturday
        (datetime(2026, 10, 18, 20, 0, tzinfo=UTC), "weekend"),  # Sunday 16:00 New York
        (datetime(2026, 10, 18, 21, 30, tzinfo=UTC), "before_window"),  # Sunday 17:30: Monday
    ],
)
def test_pending_reasons(now: datetime, reason: str) -> None:
    assert volatility.pending_reason(now) == reason


async def test_today_and_history_endpoints(
    session, client, gold, trader_headers, monkeypatch
) -> None:
    import uuid  # noqa: PLC0415

    url = "/api/v1/ai/volatility/today"
    assert (await client.get(url, params={"instrument_id": str(gold.id)})).status_code == 401
    missing = {"instrument_id": str(uuid.uuid4())}
    assert (await client.get(url, params=missing, headers=trader_headers)).status_code == 404
    pending = (
        await client.get(url, params={"instrument_id": str(gold.id)}, headers=trader_headers)
    ).json()
    today = volatility.trading_day(datetime.now(UTC))
    assert pending["status"] == "pending" and pending["day"] == today.isoformat()
    assert pending["reason"] == volatility.pending_reason(datetime.now(UTC))
    assert pending["window"] == "02:00-16:45 America/New_York" and pending["level"] is None
    for k, level in enumerate(["quiet", "very_lively", "normal"]):
        day = today - timedelta(days=2 - k)
        vol = c.Volatility.model_validate({**VOL_OK, "day": day.isoformat(), "level": level})
        assert await store.store_volatility(session, gold, f"req-{k}", vol)
    card = (
        await client.get(url, params={"instrument_id": str(gold.id)}, headers=trader_headers)
    ).json()
    assert card["status"] == "ok" and card["reason"] is None and card["day"] == today.isoformat()
    assert card["level"] == "normal" and card["level_label"] == {"ar": "عادي", "en": "Normal"}
    assert card["range_usd"] == {"p20": 24.6, "p50": 36.9, "p80": 57.4}
    assert card["news"] == [{"ts": "2026-10-19T12:30:00Z", "title": "CPI m/m", "top3": True}]
    history = (
        await client.get(
            "/api/v1/ai/volatility",
            params={"instrument_id": str(gold.id), "limit": 2},
            headers=trader_headers,
        )
    ).json()
    assert history["total"] == 3 and [i["level"] for i in history["items"]] == [
        "normal", "very_lively"]  # fmt: skip
    assert history["items"][1]["level_label"] == {"ar": "نشِط جداً", "en": "Very lively"}
    ranged = (
        await client.get(
            "/api/v1/ai/volatility",
            params={"instrument_id": str(gold.id), "from": (today - timedelta(days=2)).isoformat(),
                    "to": (today - timedelta(days=1)).isoformat()},
            headers=trader_headers,
        )
    ).json()  # fmt: skip
    assert [i["level"] for i in ranged["items"]] == ["very_lively", "quiet"]


def test_level_and_exit_labels() -> None:
    assert labels.level_label("quiet") == {"ar": "هادئ", "en": "Quiet"}
    assert labels.level_label("lively") == {"ar": "نشِط", "en": "Lively"}
    assert labels.level_label("extreme") is None and labels.level_label(None) is None
    assert labels.exit_label("trailing") == {
        "ar": "الخروج: ستوب متحرك، أو الساعة 16:45 نيويورك",
        "en": "Exit: trailing stop, or 16:45 New York",
    }
    assert labels.exit_label("target") is None and labels.exit_label(None) is None


# --- alerts --------------------------------------------------------------------------------------


@pytest.fixture
def ai() -> FakeAI:
    return FakeAI()


@pytest.fixture
def channels(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.notification_utils import TOKEN, service_account  # noqa: PLC0415

    s = get_settings()
    monkeypatch.setattr(s, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(s, "fcm_project_id", "test-project")
    monkeypatch.setattr(s, "fcm_credentials_json", json.dumps(service_account()))


async def notes(session, user_id=None) -> list[Notification]:
    query = select(Notification).where(Notification.type == NotificationType.ai_setup)
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    return list((await session.scalars(query.order_by(Notification.created_at))).all())


async def test_sl_moved_goes_to_takers_only(
    session, session_factory, redis_client, gold, make_user, ai, channels
) -> None:
    follower = await user_with_targets(make_user, session, "gl-follower@example.com", chat=71)
    taker = await user_with_targets(make_user, session, "gl-taker@example.com", chat=72,
                                    lang="en")  # fmt: skip
    for user in (follower, taker):
        session.add(AIAlertFollow(user_id=user.id, instrument_id=gold.id, profile=GL))
    await session.commit()
    await apply(session, gold, T[0], new=[gl_setup("ARMED")])
    assert await alerts.dispatch(session_factory, redis_client, client=ai.client()) == {"done": 1}
    armed = await notes(session, follower.id)
    assert [n.data["state"] for n in armed] == ["ARMED"]
    data = armed[0].data
    assert (data["exit_type"], data["tp"]) == ("trailing", None)
    assert data["exit_label"]["ar"] == "الخروج: ستوب متحرك، أو الساعة 16:45 نيويورك"
    assert armed[0].body.splitlines()[:3] == [
        "الدخول 4,100.00 · الوقف 4,090.00",
        "الخروج: ستوب متحرك، أو الساعة 16:45 نيويورك",
        "الاحتمال غير متاح",
    ]
    session.add(AISetupTake(setup_id=SETUP_ID, user_id=taker.id, lots=0.04, risk_amount=40.0))
    await session.commit()
    moved = move("ACTIVE", "ACTIVE", T[2], reason="sl_moved", sl=4094.25)
    await apply(session, gold, T[2], new=[gl_setup("ACTIVE", sl=4094.25)],
                transitions=[*HISTORY, moved])  # fmt: skip
    assert await alerts.dispatch(session_factory, redis_client, client=ai.client()) == {"done": 2}
    assert [n.data["state"] for n in await notes(session, follower.id)] == ["ARMED"]
    told = await notes(session, taker.id)
    assert [(n.data["state"], n.data.get("event")) for n in told] == [
        ("ARMED", None), ("ACTIVE", None), ("ACTIVE", "sl_moved")]  # fmt: skip
    note = told[-1]
    assert note.dedup_key == f"ai:{SETUP_ID}:sl_moved:2026-10-19T14:25:00Z"
    assert note.title == "Stop moved: BUY XAU/USD"
    assert note.body.splitlines()[:2] == [
        "New stop: 4,094.25",
        "Exit: trailing stop, or 16:45 New York",
    ]
    assert note.data["new_sl"] == 4094.25 and note.data["transition"]["sl"] == 4094.25
    assert note.severity.value == "info"
    # Arabic
    title, body = templates.inbox("ai_setup", note.data, "ar")
    assert title == "تحرّك الوقف: شراء XAU/USD" and body.startswith("الوقف الجديد: 4,094.25")


async def test_sl_moved_respects_quiet_hours_and_the_setting(
    session, session_factory, redis_client, gold, make_user, ai, channels, monkeypatch
) -> None:
    taker = await user_with_targets(make_user, session, "gl-quiet@example.com", chat=81)
    now = datetime.now(UTC)
    prefs = await prefs_mod.get_or_create(session, taker.id)
    prefs.quiet_hours = {
        "start": (now - timedelta(hours=1)).strftime("%H:%M"),
        "end": (now + timedelta(hours=1)).strftime("%H:%M"),
        "tz": "UTC",
    }
    await session.commit()
    await armed_then_active(session, gold)
    session.add(AISetupTake(setup_id=SETUP_ID, user_id=taker.id, lots=0.04, risk_amount=40.0))
    await session.commit()
    first = move("ACTIVE", "ACTIVE", T[2], reason="sl_moved", sl=4094.0)
    await apply(session, gold, T[2], new=[gl_setup("ACTIVE", sl=4094.0)],
                transitions=[*HISTORY, first])  # fmt: skip
    await alerts.dispatch(session_factory, redis_client, client=ai.client())
    [note] = [n for n in await notes(session, taker.id) if n.data.get("event") == "sl_moved"]
    holds = await session.scalars(
        select(NotificationDelivery.hold).where(NotificationDelivery.notification_id == note.id)
    )
    assert set(holds) == {"quiet_hours"}  # held for the digest, like every info alert
    # switched off after a move was enqueued: it is skipped when its turn comes
    second = move("ACTIVE", "ACTIVE", T[3], reason="sl_moved", sl=4096.0)
    await apply(session, gold, T[3], new=[gl_setup("ACTIVE", sl=4096.0)],
                transitions=[*HISTORY, first, second])  # fmt: skip
    monkeypatch.setattr(get_settings(), "ai_notify_sl_moved", False)
    assert await alerts.dispatch(session_factory, redis_client, client=ai.client()) == {
        "skipped": 1}  # fmt: skip
    row = await session.scalar(
        select(AISetupOutbox)
        .where(AISetupOutbox.sl == 4096.0)
        .execution_options(populate_existing=True)
    )
    assert row.last_error == "sl_moved notifications are off (AI_NOTIFY_SL_MOVED)"


async def test_a_setup_without_target_that_never_opened_alerts_nobody(
    session, session_factory, redis_client, gold, make_user, ai, channels
) -> None:
    taker = await user_with_targets(make_user, session, "gl-expired@example.com", chat=91)
    await apply(session, gold, T[0], new=[gl_setup("ARMED"), gl_setup("ARMED", setup_id="gl-2")])
    for setup_id in (SETUP_ID, "gl-2"):
        session.add(AISetupTake(setup_id=setup_id, user_id=taker.id, lots=0.04))
    await session.commit()
    await alerts.dispatch(session_factory, redis_client, client=ai.client())
    await apply(
        session, gold, T[1],
        transitions=[move("ARMED", "EXPIRED", T[1], reason="level_not_touched"),
                     move("ARMED", "INVALIDATED", T[1], setup_id="gl-2", reason="strategy_busy")],
    )  # fmt: skip
    assert await alerts.dispatch(session_factory, redis_client, client=ai.client()) == {"done": 2}
    assert [n.data["state"] for n in await notes(session, taker.id)] == []  # no ARMED: no follow
    states = await session.execute(
        select(AISetup.setup_id, AISetup.state).order_by(AISetup.setup_id)
    )
    assert dict(states.all()) == {"gl-2": "INVALIDATED", SETUP_ID: "EXPIRED"}
    take = await session.get(AISetupTake, ("gl-2", taker.id), populate_existing=True)
    assert take.close_reason == "strategy_busy"  # stored, with its reason


# --- Y16 without a target, the API ---------------------------------------------------------------


async def test_predictions_and_admin_views_without_a_target(
    session, session_factory, redis_client, gold, settings, client, trader_headers, admin_headers
) -> None:
    await gl_lifecycle(session, session_factory, redis_client, gold)
    page = (
        await client.get("/api/v1/predictions", params={"source": "ai", "profile": GL},
                         headers=trader_headers)
    ).json()  # fmt: skip
    outcomes = {p["id"]: (p["outcome"], p["risk_reward"], p["realized_r"]) for p in page["items"]}
    assert outcomes[f"ai:{SETUP_ID}"] == ("tp_hit", None, 1.6)  # realized_r > 0
    assert sorted(o for o, _, _ in outcomes.values()) == ["expired", "expired", "tp_hit"]
    detail = (await client.get(f"/api/v1/predictions/ai:{SETUP_ID}", headers=trader_headers)).json()
    ai = detail["ai"]
    assert (ai["exit_type"], ai["exit_reason"], ai["tp"]) == ("trailing", "trailing_stop", None)
    assert ai["exit_label"] == labels.exit_label("trailing")
    assert len(ai["sl_history"]) == 2 and ai["sl"] == ai["sl_history"][-1]["sl"]
    assert [e["sl"] for e in ai["events"] if e["reason"] == "sl_moved"] == [
        m["sl"] for m in ai["sl_history"]]  # fmt: skip
    stats = (await client.get("/api/v1/predictions/stats", params={"profile": GL},
                              headers=trader_headers)).json()  # fmt: skip
    assert stats["tp_hit_count"] == 1 and stats["mean_realized_r"] == 1.6
    admin = (await client.get(f"/api/v1/admin/ai/setups/{SETUP_ID}", headers=admin_headers)).json()
    assert admin["exit_type"] == "trailing" and admin["exit_label"]["en"].startswith("Exit:")
    assert len(admin["sl_history"]) == 2
    assert [o["sl"] is not None for o in admin["outbox"]].count(True) == 2
    listed = (await client.get("/api/v1/admin/ai/setups", params={"instrument_id": str(gold.id)},
                               headers=admin_headers)).json()  # fmt: skip
    assert {s["exit_type"] for s in listed} == {"trailing"}


async def test_follow_gold_levels_and_trades(session, client, gold, make_user, login) -> None:
    await make_user("gl-api@example.com")
    h = bearer((await login("gl-api@example.com"))["access_token"])
    res = await client.put(f"/api/v1/me/ai/follows/{gold.id}/{GL}", headers=h)
    assert res.status_code == 200 and res.json()["profile"] == GL
    await apply(session, gold, T[0], new=[gl_setup("ARMED")])
    assert (await client.post(f"/api/v1/ai/setups/{SETUP_ID}/take", json={"lots": 0.1},
                              headers=h)).status_code == 201  # fmt: skip
    [trade] = (await client.get("/api/v1/me/ai/trades", headers=h)).json()["items"]
    assert (trade["exit_type"], trade["tp"]) == ("trailing", None)
    assert trade["exit_label"]["ar"].startswith("الخروج")
