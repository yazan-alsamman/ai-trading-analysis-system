"""B8 AI storage: apply_evaluation (idempotent, final states, the transition table, rejections),
open_setups (exact echo), the model registry and the admin endpoints."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import contract as c
from app.ai import store
from app.models.ai import AIModelVersion, AISetup, AISetupEvent
from app.models.instrument import Instrument
from tests.market_utils import make_instrument

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api" / "ai-service-examples"
OPEN_ID = "xauusd-intraday-2026-10-19T09:30:00Z-buy"
NEW_ID = "xauusd-intraday-2026-10-19T14:15:00Z-buy"
VERSIONS = {"strategy": "xau-intraday-1.0.0", "model": "lgbm-2026-10-01", "features": "f-3"}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def request_at(close: datetime, open_setups: list[dict] | None = None) -> c.EvaluateRequest:
    base = load("evaluate-request")
    bar = {"ts": c.iso_z(close - timedelta(minutes=15)), "o": 2400, "h": 2401, "l": 2399, "c": 2400}
    return c.EvaluateRequest.model_validate(
        {
            **base,
            "request_id": c.make_request_id("XAUUSD", "intraday", close),
            "bar_close_ts": c.iso_z(close),
            "bars": {"15m": [bar]},
            "open_setups": open_setups or [],
        }
    )


def response(req: c.EvaluateRequest, *, new=(), transitions=(), status="ok", versions=None):
    return c.EvaluateResponse.model_validate(
        {
            "request_id": req.request_id,
            "status": status,
            "versions": versions or VERSIONS,
            "new_setups": list(new),
            "transitions": list(transitions),
            "abstentions": [],
        }
    )


def setup(setup_id: str, state: str, **changes) -> dict:
    return {**load("evaluate-response-ok")["new_setups"][0], "setup_id": setup_id, "state": state,
            **changes}  # fmt: skip


def move(setup_id: str, frm: str, to: str, at: datetime, **extra) -> dict:
    return {"setup_id": setup_id, "from": frm, "to": to, "at": c.iso_z(at), **extra}


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    return await make_instrument(session, symbol="XAU/USD", source="fxpro")


async def counts(session: AsyncSession) -> tuple[int, int]:
    setups = await session.scalar(select(func.count()).select_from(AISetup))
    events = await session.scalar(select(func.count()).select_from(AISetupEvent))
    return setups, events


async def events_of(session: AsyncSession, setup_id: str) -> list[tuple]:
    rows = await session.execute(
        select(AISetupEvent.from_state, AISetupEvent.to_state, AISetupEvent.realized_r)
        .where(AISetupEvent.setup_id == setup_id)
        .order_by(AISetupEvent.at, AISetupEvent.id)
    )
    return [tuple(r) for r in rows.all()]


async def seed_open_setup(session: AsyncSession, gold: Instrument) -> None:
    """The ACTIVE setup the example request carries, as an earlier response created it."""
    earlier = request_at(utc(2026, 10, 19, 9, 30))
    opened = load("evaluate-request")["open_setups"][0]
    await store.apply_evaluation(session, gold, earlier, response(earlier, new=[opened]))


async def test_apply_the_ok_example_twice(session: AsyncSession, gold: Instrument) -> None:
    await seed_open_setup(session, gold)
    req = c.EvaluateRequest.model_validate(load("evaluate-request"))
    resp = c.EvaluateResponse.model_validate(load("evaluate-response-ok"))

    first = await store.apply_evaluation(session, gold, req, resp)
    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)
    assert (first.transitions_applied, first.rejected) == (1, [])
    assert [(s.setup_id, s.from_state, s.to_state) for s in first.state_changes] == [
        (NEW_ID, None, "ARMED"),
        (OPEN_ID, "ACTIVE", "CLOSED"),
    ]
    assert first.state_changes[1].realized_r == 2.0 and first.status == "ok"
    after_first = await counts(session)
    assert after_first == (2, 3)

    second = await store.apply_evaluation(session, gold, req, resp)  # a re-applied response
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)
    assert (second.transitions_applied, second.transitions_known) == (0, 1)
    assert second.state_changes == [] and second.rejected == []
    assert await counts(session) == after_first

    row = await session.get(AISetup, NEW_ID, populate_existing=True)
    assert (row.state, row.entry, row.grade, row.model_version) == (
        "ARMED",
        2400.0,
        "B",
        VERSIONS["model"],
    )
    assert row.first_request_id == req.request_id and row.evidence["trend_4h"] == "up"
    closed = await session.get(AISetup, OPEN_ID, populate_existing=True)
    assert (closed.state, closed.realized_r) == ("CLOSED", 2.0)
    assert closed.last_payload["state"] == "CLOSED"
    model = await session.get(AIModelVersion, VERSIONS["model"])
    assert model is not None and not model.is_active  # reported, recorded inactive


async def test_armed_active_closed_chain(session: AsyncSession, gold: Instrument) -> None:
    t0 = utc(2026, 10, 19, 14, 15)
    r1 = request_at(t0)
    await store.apply_evaluation(session, gold, r1, response(r1, new=[setup(NEW_ID, "ARMED")]))
    r2 = request_at(t0 + timedelta(minutes=15), await store.open_setups(session, gold, "intraday"))
    res2 = await store.apply_evaluation(
        session, gold, r2,
        response(r2, transitions=[move(NEW_ID, "ARMED", "ACTIVE", t0 + timedelta(minutes=7),
                                       reason="entry_filled")]),
    )  # fmt: skip
    assert [(s.from_state, s.to_state) for s in res2.state_changes] == [("ARMED", "ACTIVE")]
    r3 = request_at(t0 + timedelta(minutes=30), await store.open_setups(session, gold, "intraday"))
    assert [s.state for s in r3.open_setups] == [c.SetupState.ACTIVE]
    res3 = await store.apply_evaluation(
        session, gold, r3,
        response(r3, transitions=[move(NEW_ID, "ACTIVE", "CLOSED", t0 + timedelta(minutes=26),
                                       reason="sl_hit", realized_r=-1.0)]),
    )  # fmt: skip
    assert res3.state_changes[0].realized_r == -1.0
    assert await events_of(session, NEW_ID) == [
        (None, "ARMED", None),
        ("ARMED", "ACTIVE", None),
        ("ACTIVE", "CLOSED", -1.0),
    ]
    row = await session.get(AISetup, NEW_ID, populate_existing=True)
    assert (row.state, row.realized_r, row.last_request_id) == ("CLOSED", -1.0, r3.request_id)
    assert await store.open_setups(session, gold, "intraday") == []


async def test_illegal_transitions_are_rejected_the_rest_applies(
    session: AsyncSession, gold: Instrument, caplog
) -> None:
    t0 = utc(2026, 10, 19, 14, 15)
    r1 = request_at(t0)
    await store.apply_evaluation(
        session,
        gold,
        r1,
        response(r1, new=[setup("closed-one", "CLOSED"), setup("armed", "ARMED")]),
    )
    r2 = request_at(t0 + timedelta(minutes=15))
    result = await store.apply_evaluation(
        session, gold, r2,
        response(
            r2,
            new=[setup("brand-new", "ARMED")],
            transitions=[
                move("closed-one", "CLOSED", "ACTIVE", t0 + timedelta(minutes=5)),  # final
                move("armed", "ARMED", "CLOSED", t0 + timedelta(minutes=6)),  # not in the table
                move("armed", "DEVELOPING", "ARMED", t0 + timedelta(minutes=7)),  # wrong from
                move("ghost", "ARMED", "ACTIVE", t0 + timedelta(minutes=8)),  # unknown
                move("armed", "ARMED", "INVALIDATED", t0 + timedelta(minutes=9), reason="news"),
            ],
        ),
    )  # fmt: skip
    assert [(r.setup_id, r.reason) for r in result.rejected] == [
        ("closed-one", "CLOSED is final (CLOSED -> ACTIVE)"),
        ("armed", "ARMED -> CLOSED is not allowed"),
        ("armed", "from DEVELOPING but the setup is ARMED"),
        ("ghost", "unknown setup_id"),
    ]
    assert (result.inserted, result.transitions_applied) == (1, 1)  # the rest was applied
    assert [(s.setup_id, s.to_state) for s in result.state_changes] == [
        ("brand-new", "ARMED"),
        ("armed", "INVALIDATED"),
    ]
    assert (await session.get(AISetup, "closed-one")).state == "CLOSED"
    assert caplog.text.count("ai-service result rejected") == 4


async def test_new_setups_never_move_a_state_backwards(
    session: AsyncSession, gold: Instrument
) -> None:
    t0 = utc(2026, 10, 19, 14, 15)
    r1 = request_at(t0)
    developing = setup("s1", "DEVELOPING", entry=None, sl=None, tp=None)
    await store.apply_evaluation(session, gold, r1, response(r1, new=[developing]))
    r2 = request_at(t0 + timedelta(minutes=15))
    res = await store.apply_evaluation(session, gold, r2, response(r2, new=[setup("s1", "ARMED")]))
    assert [(s.from_state, s.to_state) for s in res.state_changes] == [("DEVELOPING", "ARMED")]
    assert res.updated == 1
    r3 = request_at(t0 + timedelta(minutes=30))
    trans = [move("s1", "ARMED", "ACTIVE", t0 + timedelta(minutes=20))]
    await store.apply_evaluation(session, gold, r3, response(r3, transitions=trans))
    # ai-service repeats it as ARMED with a new stop: prices update, the state stays ACTIVE
    r4 = request_at(t0 + timedelta(minutes=45))
    res = await store.apply_evaluation(
        session, gold, r4, response(r4, new=[setup("s1", "ARMED", sl=2396.0)])
    )
    assert res.state_changes == [] and res.updated == 1
    row = await session.get(AISetup, "s1", populate_existing=True)
    assert (row.state, row.sl, row.last_payload["state"], row.last_payload["sl"]) == (
        "ACTIVE", 2396.0, "ACTIVE", 2396.0,
    )  # fmt: skip
    # a final setup sent again is left as it is
    r5 = request_at(t0 + timedelta(minutes=60))
    trans = [move("s1", "ACTIVE", "CLOSED", t0 + timedelta(minutes=50), realized_r=1.5)]
    await store.apply_evaluation(session, gold, r5, response(r5, transitions=trans))
    r6 = request_at(t0 + timedelta(minutes=75))
    res = await store.apply_evaluation(
        session, gold, r6, response(r6, new=[setup("s1", "ARMED", tp=2420.0)])
    )
    assert res.unchanged == 1 and res.updated == 0
    row = await session.get(AISetup, "s1", populate_existing=True)
    assert (row.state, row.tp, row.realized_r) == ("CLOSED", 2410.0, 1.5)


async def test_status_not_ok_stores_only_the_versions(
    session: AsyncSession, gold: Instrument
) -> None:
    req = c.EvaluateRequest.model_validate(load("evaluate-request"))
    unavailable = c.EvaluateResponse.model_validate(load("evaluate-response-model-unavailable"))
    result = await store.apply_evaluation(session, gold, req, unavailable)
    assert result.status == "model_unavailable" and result.versions["model"] is None
    assert result.state_changes == [] and await counts(session) == (0, 0)
    assert await session.scalar(select(func.count()).select_from(AIModelVersion)) == 0

    failed = response(req, new=[setup("x", "ARMED")], status="data_quality_failed")
    result = await store.apply_evaluation(session, gold, req, failed)
    assert result.status == "data_quality_failed" and await counts(session) == (0, 0)
    assert await session.get(AIModelVersion, VERSIONS["model"]) is not None

    with pytest.raises(ValueError, match="is not for request"):
        await store.apply_evaluation(session, gold, request_at(utc(2026, 1, 5, 10)), failed)


async def test_open_setups_echo_last_payload(session: AsyncSession, gold: Instrument) -> None:
    other = await make_instrument(session, symbol="EUR/USD", source="fxpro")
    t0 = utc(2026, 10, 19, 14, 15)
    r1 = request_at(t0)
    sent = [
        setup("b-armed", "ARMED", entry=2400, regime={"kind": "trend", "score": 0.7}),
        setup("a-developing", "DEVELOPING", valid_until="2026-10-19T15:15:00+00:00"),
        setup("c-expired", "EXPIRED"),
    ]
    await store.apply_evaluation(session, gold, r1, response(r1, new=sent))
    await store.apply_evaluation(session, other, r1, response(r1, new=[setup("eur", "ARMED")]))
    echoed = await store.open_setups(session, gold, "intraday")
    # the same JSON values as returned (2400 stays an int, the +00:00 offset is kept); JSONB
    # does not keep the key order. Oldest first, then by setup_id (one response: same time)
    assert echoed == [sent[1], sent[0]]
    assert await store.open_setups(session, gold, "swing") == []
    # the next request carries them unchanged
    r2 = request_at(t0 + timedelta(minutes=15), echoed)
    assert r2.model_dump(mode="json")["open_setups"] == copy.deepcopy([sent[1], sent[0]])


async def test_one_active_model(session: AsyncSession) -> None:
    await store.register_model(session, "m1", metrics={"auc": 0.61}, notes="first")
    await store.register_model(
        session, "m2", training_from=utc(2018, 1, 1), training_to=utc(2026, 9, 30), data_hash="abc"
    )
    assert (await store.activate_model(session, "m1")).is_active
    m2 = await store.activate_model(session, "m2")
    assert m2.is_active and m2.data_hash == "abc"
    active = await session.scalars(
        select(AIModelVersion.model_id).where(AIModelVersion.is_active.is_(True))
    )
    assert list(active) == ["m2"]
    assert await store.activate_model(session, "missing") is None
    again = await store.register_model(session, "m1", metrics={"auc": 0.63})
    assert again.metrics == {"auc": 0.63} and not again.is_active
    with pytest.raises(IntegrityError):  # the partial unique index
        await session.execute(update(AIModelVersion).values(is_active=True))
    await session.rollback()


async def test_admin_endpoints(
    client: AsyncClient, session: AsyncSession, gold: Instrument, admin_headers, trader_headers
) -> None:
    await seed_open_setup(session, gold)
    req = c.EvaluateRequest.model_validate(load("evaluate-request"))
    await store.apply_evaluation(
        session, gold, req, c.EvaluateResponse.model_validate(load("evaluate-response-ok"))
    )
    for method, url in (
        ("get", "/api/v1/admin/ai/setups"),
        ("get", f"/api/v1/admin/ai/setups/{NEW_ID}"),
        ("get", "/api/v1/admin/ai/models"),
        ("post", "/api/v1/admin/ai/models/m1/activate"),
    ):
        assert (await client.request(method, url, headers=trader_headers)).status_code == 403
        assert (await client.request(method, url)).status_code == 401
    res = await client.post(
        "/api/v1/admin/ai/models", json={"model_id": "m1"}, headers=trader_headers
    )
    assert res.status_code == 403

    res = await client.get("/api/v1/admin/ai/setups", headers=admin_headers)
    assert [s["setup_id"] for s in res.json()] == [NEW_ID, OPEN_ID]
    res = await client.get(
        "/api/v1/admin/ai/setups", params={"state": "CLOSED"}, headers=admin_headers
    )
    assert [s["setup_id"] for s in res.json()] == [OPEN_ID]
    res = await client.get(f"/api/v1/admin/ai/setups/{OPEN_ID}", headers=admin_headers)
    detail = res.json()
    assert [(e["from_state"], e["to_state"]) for e in detail["events"]] == [
        (None, "ACTIVE"),
        ("ACTIVE", "CLOSED"),
    ]
    assert detail["last_payload"]["state"] == "CLOSED" and detail["realized_r"] == 2.0
    missing = await client.get("/api/v1/admin/ai/setups/nope", headers=admin_headers)
    assert missing.status_code == 404

    res = await client.post(
        "/api/v1/admin/ai/models",
        json={"model_id": "lgbm-2026-11-01", "metrics": {"auc": 0.62}, "notes": "retrained"},
        headers=admin_headers,
    )
    assert res.status_code == 200 and res.json()["is_active"] is False
    res = await client.post(
        "/api/v1/admin/ai/models/lgbm-2026-11-01/activate", headers=admin_headers
    )
    assert res.json()["is_active"] is True
    models = (await client.get("/api/v1/admin/ai/models", headers=admin_headers)).json()
    assert {m["model_id"]: m["is_active"] for m in models} == {
        "lgbm-2026-11-01": True,
        VERSIONS["model"]: False,  # reported by the example response
    }
    res = await client.post("/api/v1/admin/ai/models/nope/activate", headers=admin_headers)
    assert res.status_code == 404
