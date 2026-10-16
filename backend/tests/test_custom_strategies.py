"""/me/custom-strategies and /custom-strategies/*: CRUD, limits per role, unique names,
versions, visibility, cloning, ownership, deletion rules, schema, validation and API keys."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.models.user import UserRole
from tests.api_key_utils import create_key, xkey
from tests.custom_utils import (
    MA_REPLICA,
    MINE,
    PUBLIC,
    body,
    composite,
    cond,
    const,
    create,
    ind,
    rsi_below,
)
from tests.market_utils import make_instrument
from tests.utils import bearer

SCHEMA = "/api/v1/custom-strategies/schema"
VALIDATE = "/api/v1/custom-strategies/validate"


@pytest.fixture
def make_headers(make_user, session: AsyncSession):
    async def _make(email: str, role: UserRole = UserRole.trader, full_name: str | None = None):
        user = await make_user(email, role=role)
        if full_name:
            user.full_name = full_name
            await session.commit()
        return user, bearer(create_access_token(user))

    return _make


@pytest.fixture
async def trader(make_headers):
    return await make_headers("trader@example.com")


@pytest.fixture
async def analyst(make_headers):
    return await make_headers("analyst@example.com", UserRole.analyst, "Ana Lyst")


# --- create / read / list ---------------------------------------------------------------------


async def test_create_read_list(client: AsyncClient, trader) -> None:
    _, headers = trader
    created = await create(client, headers, "EMA cross", MA_REPLICA, description="9/21")
    assert created["key"] == f"custom:{created['id']}"
    assert (created["kind"], created["visibility"], created["version"]) == (
        "builder",
        "private",
        1,
    )
    assert created["valid"] is True and created["errors"] == [] and created["history"] > 0
    assert created["usage"] == {
        "activations": 0,
        "active_activations": 0,
        "backtests": 0,
        "composites": 0,
    }
    assert created["cloned_from"] is None and len(created["definition_hash"]) == 32
    # stored normalised: defaults and single outputs explicit
    left = created["definition"]["buy"]["all"][0]["left"]
    assert left == {
        "type": "indicator",
        "name": "ema",
        "params": {"length": 9},
        "output": "ema",
        "shift": 0,
    }
    assert created["definition"]["strength"] == "fixed"

    res = await client.get(f"{MINE}/{created['id']}", headers=headers)
    assert res.status_code == 200 and res.json() == created
    await create(client, headers, "Oversold", rsi_below(25))
    page = (await client.get(MINE, headers=headers)).json()
    assert page["total"] == 2 and [i["name"] for i in page["items"]] == ["EMA cross", "Oversold"]
    assert "definition" not in page["items"][0]
    only = (await client.get(MINE, params={"kind": "composite"}, headers=headers)).json()
    assert only["total"] == 0


async def test_invalid_definition_422_with_paths(client: AsyncClient, trader) -> None:
    _, headers = trader
    bad = rsi_below(30)
    bad["buy"]["all"][0]["left"]["params"]["length"] = 0
    bad["sell"] = {"any": [cond(ind("macd"), ">", const(0))]}
    res = await client.post(MINE, json=body("Bad", bad), headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"] == [
        {
            "loc": ["body", "definition", "buy", "all", 0, "left", "params", "length"],
            "msg": "length must be between 1 and 1000, got 0",
            "type": "value_error",
            "path": "buy.all[0].left.params.length",
        },
        {
            "loc": ["body", "definition", "sell", "any", 0, "left", "output"],
            "msg": "required: macd has several outputs (macd, signal, histogram)",
            "type": "value_error",
            "path": "sell.any[0].left.output",
        },
    ]
    # the wrong kind for the document
    res = await client.post(MINE, json=body("Bad", MA_REPLICA, kind="composite"), headers=headers)
    assert res.status_code == 422 and res.json()["detail"][0]["path"] == "members"
    for extra in ({"name": ""}, {"name": "x" * 61}, {"description": "x" * 501}, {"kind": "x"}):
        res = await client.post(MINE, json={**body("Ok", MA_REPLICA), **extra}, headers=headers)
        assert res.status_code == 422, extra


async def test_names_are_unique_per_user_case_insensitive(
    client: AsyncClient, trader, analyst
) -> None:
    _, headers = trader
    first = await create(client, headers, "My Rule", MA_REPLICA)
    res = await client.post(MINE, json=body("my rule", MA_REPLICA), headers=headers)
    assert res.status_code == 409
    await create(client, analyst[1], "MY RULE", MA_REPLICA)  # another user: fine
    other = await create(client, headers, "Other", MA_REPLICA)
    res = await client.patch(f"{MINE}/{other['id']}", json={"name": "MY rule"}, headers=headers)
    assert res.status_code == 409
    res = await client.put(
        f"{MINE}/{other['id']}",
        json={"version": 1, "definition": MA_REPLICA, "name": "my RULE"},
        headers=headers,
    )
    assert res.status_code == 409
    res = await client.patch(f"{MINE}/{first['id']}", json={"name": "my rule"}, headers=headers)
    assert res.status_code == 200 and res.json()["name"] == "my rule"  # own name, new case


async def test_limits_per_role(client: AsyncClient, trader, analyst, monkeypatch) -> None:
    settings = get_settings()
    assert settings.custom_strategy_limit("trader") == 5
    assert settings.custom_strategy_limit("analyst") == 50
    assert settings.custom_strategy_limit("expert") == 50
    assert settings.custom_strategy_limit("admin") == 50
    _, headers = trader
    for i in range(5):
        await create(client, headers, f"S{i}", MA_REPLICA)
    res = await client.post(MINE, json=body("S5", MA_REPLICA), headers=headers)
    assert res.status_code == 400 and "At most 5" in res.json()["detail"]
    first = (await client.get(MINE, headers=headers)).json()["items"][0]["id"]
    assert (await client.post(f"{MINE}/{first}/clone", headers=headers)).status_code == 400

    monkeypatch.setattr(settings, "custom_strategy_limit_analyst", 7)
    for i in range(7):
        await create(client, analyst[1], f"A{i}", MA_REPLICA)
    res = await client.post(MINE, json=body("A7", MA_REPLICA), headers=analyst[1])
    assert res.status_code == 400 and "At most 7" in res.json()["detail"]


# --- PUT (versions) / PATCH -------------------------------------------------------------------


async def test_put_replaces_the_definition_with_versions(client: AsyncClient, trader) -> None:
    _, headers = trader
    created = await create(client, headers, "Oversold", rsi_below(30))
    url = f"{MINE}/{created['id']}"
    res = await client.put(url, json={"version": 1, "definition": rsi_below(25)}, headers=headers)
    assert res.status_code == 200, res.text
    v2 = res.json()
    assert v2["version"] == 2 and v2["definition_hash"] != created["definition_hash"]
    assert v2["definition"]["buy"]["all"][0]["right"]["value"] == 25.0

    stale = await client.put(url, json={"version": 1, "definition": rsi_below(20)}, headers=headers)
    assert stale.status_code == 409
    assert stale.json()["current_version"] == 2 and stale.headers["etag"] == '"2"'

    # same definition (written differently): no new version, name/description still change
    same = rsi_below(25)
    same["buy"]["all"][0]["left"]["params"] = {}  # default length 14
    res = await client.put(
        url,
        json={"version": 2, "definition": same, "name": "Deep", "description": "RSI < 25"},
        headers=headers,
    )
    assert res.status_code == 200
    assert (res.json()["version"], res.json()["name"], res.json()["description"]) == (
        2,
        "Deep",
        "RSI < 25",
    )
    assert res.json()["definition_hash"] == v2["definition_hash"]

    bad = rsi_below(25)
    bad["buy"]["all"][0]["op"] = "=="
    res = await client.put(url, json={"version": 2, "definition": bad}, headers=headers)
    assert res.status_code == 422 and res.json()["detail"][0]["path"] == "buy.all[0].op"
    res = await client.put(url, json={"definition": rsi_below(1)}, headers=headers)
    assert res.status_code == 422  # version is required


async def test_patch_fields(client: AsyncClient, trader) -> None:
    _, headers = trader
    created = await create(client, headers, "Rule", MA_REPLICA)
    url = f"{MINE}/{created['id']}"
    res = await client.patch(url, json={"description": "notes"}, headers=headers)
    assert res.status_code == 200 and res.json()["description"] == "notes"
    assert res.json()["version"] == 1  # metadata only
    for bad in ({"name": None}, {"visibility": "friends"}, {"definition": MA_REPLICA}):
        assert (await client.patch(url, json=bad, headers=headers)).status_code == 422


async def test_visibility_rules(client: AsyncClient, trader, analyst) -> None:
    _, t_headers = trader
    _, a_headers = analyst
    mine = await create(client, t_headers, "Mine", MA_REPLICA)
    res = await client.patch(
        f"{MINE}/{mine['id']}", json={"visibility": "public"}, headers=t_headers
    )
    assert res.status_code == 403
    res = await client.post(
        MINE, json=body("Pub", MA_REPLICA, visibility="public"), headers=t_headers
    )
    assert res.status_code == 403

    member = await create(client, a_headers, "Member", rsi_below(30))
    comp = await create(client, a_headers, "Combo", composite("rsi_reversal", member["key"]))
    res = await client.patch(
        f"{MINE}/{comp['id']}", json={"visibility": "public"}, headers=a_headers
    )
    assert res.status_code == 409 and "Member" in res.json()["detail"]
    for target in (member, comp):
        res = await client.patch(
            f"{MINE}/{target['id']}", json={"visibility": "public"}, headers=a_headers
        )
        assert res.status_code == 200 and res.json()["visibility"] == "public"
    # a member of one of your public composites cannot go private
    res = await client.patch(
        f"{MINE}/{member['id']}", json={"visibility": "private"}, headers=a_headers
    )
    assert res.status_code == 409 and "Combo" in res.json()["detail"]
    for target in (comp, member):
        res = await client.patch(
            f"{MINE}/{target['id']}", json={"visibility": "private"}, headers=a_headers
        )
        assert res.status_code == 200


# --- clone / public ---------------------------------------------------------------------------


async def test_clone_own(client: AsyncClient, trader) -> None:
    _, headers = trader
    source = await create(client, headers, "Rule", MA_REPLICA)
    res = await client.post(f"{MINE}/{source['id']}/clone", headers=headers)
    assert res.status_code == 201
    copy = res.json()
    assert (copy["name"], copy["visibility"], copy["cloned_from"]) == (
        "Rule (copy)",
        "private",
        source["id"],
    )
    assert copy["id"] != source["id"] and copy["definition"] == source["definition"]
    assert copy["definition_hash"] == source["definition_hash"]  # same setup, same hash
    again = (await client.post(f"{MINE}/{source['id']}/clone", headers=headers)).json()
    assert again["name"] == "Rule (copy 2)"


async def test_public_list_and_clone(client: AsyncClient, trader, analyst) -> None:
    trader_user, t_headers = trader
    _, a_headers = analyst
    shared = await create(
        client, a_headers, "Deep RSI", rsi_below(20), visibility="public", description="d"
    )
    await create(client, a_headers, "Secret", rsi_below(10))  # private: never listed
    await create(client, a_headers, "Trend", MA_REPLICA, visibility="public")

    page = (await client.get(PUBLIC, headers=t_headers)).json()
    assert page["total"] == 2
    assert [i["name"] for i in page["items"]] == ["Trend", "Deep RSI"]  # newest first
    item = page["items"][1]
    assert item["author"] == {"display_name": "Ana Lyst", "role": "analyst"}
    assert item["key"] == shared["key"] and item["definition"] == shared["definition"]
    assert "user_id" not in item and "cloned_from" not in item
    found = (await client.get(PUBLIC, params={"search": "rsi"}, headers=t_headers)).json()
    assert [i["name"] for i in found["items"]] == ["Deep RSI"]
    found = (await client.get(PUBLIC, params={"search": "%"}, headers=t_headers)).json()
    assert found["total"] == 0  # LIKE wildcards are literal

    res = await client.post(f"{PUBLIC}/{shared['id']}/clone", headers=t_headers)
    assert res.status_code == 201
    copy = res.json()
    assert (copy["name"], copy["visibility"], copy["cloned_from"]) == (
        "Deep RSI",
        "private",
        shared["id"],
    )
    again = await client.post(f"{PUBLIC}/{shared['id']}/clone", headers=t_headers)
    assert again.json()["name"] == "Deep RSI (copy)"
    secret_id = next(
        i["id"]
        for i in (await client.get(MINE, headers=a_headers)).json()["items"]
        if i["name"] == "Secret"
    )
    assert (await client.post(f"{PUBLIC}/{secret_id}/clone", headers=t_headers)).status_code == 404
    assert (
        await client.post(f"{PUBLIC}/{uuid.uuid4()}/clone", headers=t_headers)
    ).status_code == 404
    # the caller's limit applies
    for i in range(3):
        await create(client, t_headers, f"T{i}", MA_REPLICA)
    res = await client.post(f"{PUBLIC}/{shared['id']}/clone", headers=t_headers)
    assert res.status_code == 400
    assert trader_user.role == UserRole.trader


async def test_ownership_is_404(client: AsyncClient, trader, analyst) -> None:
    _, t_headers = trader
    _, a_headers = analyst
    theirs = await create(client, a_headers, "Theirs", MA_REPLICA, visibility="public")
    url = f"{MINE}/{theirs['id']}"
    put = {"version": 1, "definition": MA_REPLICA}
    assert (await client.get(url, headers=t_headers)).status_code == 404
    assert (await client.put(url, json=put, headers=t_headers)).status_code == 404
    assert (await client.patch(url, json={"name": "x"}, headers=t_headers)).status_code == 404
    assert (await client.delete(url, headers=t_headers)).status_code == 404
    assert (await client.post(f"{url}/clone", headers=t_headers)).status_code == 404
    assert (await client.get(f"{MINE}/{uuid.uuid4()}", headers=t_headers)).status_code == 404
    # still there for its owner
    assert (await client.get(url, headers=a_headers)).status_code == 200


# --- delete -----------------------------------------------------------------------------------


async def test_delete_deactivates_and_keeps_signals(
    client: AsyncClient, session: AsyncSession, trader
) -> None:
    user, headers = trader
    btc = await make_instrument(session, "BTC/USDT")
    created = await create(client, headers, "Rule", MA_REPLICA)
    res = await client.post(
        "/api/v1/me/strategies",
        json={"strategy_key": created["key"], "instrument_id": str(btc.id), "timeframe": "1h"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    activation_id = res.json()["id"]
    signal = Signal(
        instrument_id=btc.id,
        timeframe="1h",
        strategy_key=created["key"],
        params={},
        params_hash=created["definition_hash"],
        bar_time=datetime(2026, 3, 2, 12, tzinfo=UTC),
        side=SignalSide.buy,
        strength=1.0,
        price=1.0,
        reason="builder_buy",
        details={},
    )
    session.add(signal)
    await session.commit()
    detail = (await client.get(f"{MINE}/{created['id']}", headers=headers)).json()
    assert detail["usage"]["activations"] == detail["usage"]["active_activations"] == 1

    assert (await client.delete(f"{MINE}/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{MINE}/{created['id']}", headers=headers)).status_code == 404
    row = await session.get(UserStrategy, uuid.UUID(activation_id), populate_existing=True)
    assert row is not None and row.is_active is False
    kept = await session.scalars(select(Signal).where(Signal.strategy_key == created["key"]))
    assert len(kept.all()) == 1
    # re-activating it is refused: the strategy is gone
    res = await client.patch(
        f"/api/v1/me/strategies/{activation_id}", json={"is_active": True}, headers=headers
    )
    assert res.status_code == 404
    assert user.id == row.user_id


async def test_delete_refused_while_a_composite_uses_it(client: AsyncClient, trader) -> None:
    _, headers = trader
    member = await create(client, headers, "Member", rsi_below(30))
    await create(client, headers, "Combo A", composite("macd_cross", member["key"]))
    await create(client, headers, "Combo B", composite(member["key"], "rsi_reversal"))
    res = await client.delete(f"{MINE}/{member['id']}", headers=headers)
    assert res.status_code == 409
    assert res.json()["detail"] == (
        "Used by your composite(s): Combo A, Combo B; remove it from them first"
    )
    detail = (await client.get(f"{MINE}/{member['id']}", headers=headers)).json()
    assert detail["usage"]["composites"] == 2


# --- schema / validate / API keys -------------------------------------------------------------


async def test_schema(client: AsyncClient, trader) -> None:
    _, headers = trader
    res = await client.get(SCHEMA, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert set(data["json_schema"]) == {"builder", "composite"}
    assert data["json_schema"]["builder"]["additionalProperties"] is False
    catalog = data["catalog"]
    names = {i["name"] for i in catalog["builder"]["indicators"]}
    assert {"rsi", "ema", "bollinger", "macd"} <= names
    assert catalog["builder"]["price_fields"][-3:] == ["hl2", "hlc3", "ohlc4"]
    assert {o["op"] for o in catalog["builder"]["ops"]} == {
        ">", "<", ">=", "<=", "crosses_above", "crosses_below", "between", "rising", "falling"
    }  # fmt: skip
    assert catalog["composite"]["modes"] == ["all", "any", "majority", "weighted"]
    assert catalog["limits"]["max_conditions"] == 50
    assert (await client.get(SCHEMA)).status_code == 401


async def test_validate(client: AsyncClient, trader) -> None:
    _, headers = trader
    res = await client.post(
        VALIDATE, json={"kind": "builder", "definition": MA_REPLICA}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True and data["errors"] == [] and data["history"] > 0
    assert len(data["definition_hash"]) == 32 and data["definition"]["category"] == "trend"

    bad = rsi_below(30)
    bad["buy"]["all"][0]["left"]["params"] = {"length": 0}
    res = await client.post(VALIDATE, json={"kind": "builder", "definition": bad}, headers=headers)
    assert res.status_code == 200
    assert res.json()["valid"] is False and res.json()["history"] is None
    assert res.json()["errors"] == [
        {
            "path": "buy.all[0].left.params.length",
            "loc": ["buy", "all", 0, "left", "params", "length"],
            "message": "length must be between 1 and 1000, got 0",
        }
    ]
    for payload in (
        None,
        [1, 2],
        {"kind": "python", "definition": {}},
        {"definition": MA_REPLICA},
        {"kind": "builder"},
        {"kind": "builder", "definition": MA_REPLICA, "extra": 1},
        {"kind": "composite", "definition": "text"},
        {"kind": "builder", "definition": MA_REPLICA, "id": "nope"},
    ):
        res = await client.post(VALIDATE, json=payload, headers=headers)
        assert res.status_code == 200, payload
        assert res.json()["valid"] is False and res.json()["errors"], payload
    res = await client.post(VALIDATE, content=b"not json", headers=headers)
    assert res.status_code == 200 and res.json()["valid"] is False


async def test_validate_detects_cycles_with_id(client: AsyncClient, trader) -> None:
    _, headers = trader
    member = await create(client, headers, "Member", rsi_below(30))
    combo = await create(client, headers, "Combo", composite("macd_cross", member["key"]))
    outer = await create(client, headers, "Outer", composite("rsi_reversal", combo["key"]))
    looped = composite("rsi_reversal", outer["key"])
    payload = {"kind": "composite", "definition": looped, "id": combo["id"]}
    res = await client.post(VALIDATE, json=payload, headers=headers)
    errors = res.json()["errors"]
    assert res.json()["valid"] is False and "cycle:" in errors[0]["message"]
    put = {"version": 1, "definition": looped}
    res = await client.put(f"{MINE}/{combo['id']}", json=put, headers=headers)
    assert res.status_code == 422 and "cycle:" in res.json()["detail"][0]["msg"]


async def test_validate_costs_2(client: AsyncClient, rate_limits, trader) -> None:
    _, headers = trader
    payload = {"kind": "builder", "definition": MA_REPLICA}
    first = await client.post(VALIDATE, json=payload, headers=headers)
    second = await client.post(VALIDATE, json=payload, headers=headers)
    assert int(first.headers["ratelimit-remaining"]) == 60 - 2
    assert int(second.headers["ratelimit-remaining"]) == 60 - 4


async def test_api_keys(client: AsyncClient, trader, analyst) -> None:
    _, headers = trader
    await create(client, analyst[1], "Shared", MA_REPLICA, visibility="public")
    with_scope = await create_key(client, headers, ["strategies:read"])
    without = await create_key(client, headers, ["market:read"], name="other")
    for path in (SCHEMA, PUBLIC):
        assert (await client.get(path, headers=xkey(with_scope["key"]))).status_code == 200
        res = await client.get(path, headers=xkey(without["key"]))
        assert res.status_code == 403
        assert res.json()["detail"] == "This API key lacks the 'strategies:read' scope"
    payload = {"kind": "builder", "definition": MA_REPLICA}
    for method, path, json in (
        ("GET", MINE, None),
        ("POST", MINE, body("x", MA_REPLICA)),
        ("POST", VALIDATE, payload),
    ):
        res = await client.request(method, path, json=json, headers=xkey(with_scope["key"]))
        assert res.status_code == 403, path
        assert res.json()["detail"] == "API keys cannot be used for this endpoint"
    assert (await client.get(MINE)).status_code == 401
