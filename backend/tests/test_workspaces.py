"""/me/workspaces and shared workspaces: default creation, templates, limits, names, state
validation, versions (409), default handling, order, duplicate, delete, unavailable
instruments, sharing, access rules and the workspace_updated WebSocket message."""

import asyncio
import copy
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.session import get_session
from app.main import app
from app.models.instrument import Instrument
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.realtime.hub import WebSocketHub
from tests.api_key_utils import create_key, xkey
from tests.market_utils import make_instrument
from tests.utils import DEFAULT_PASSWORD, bearer
from tests.ws_utils import recv, recv_until, ws_connect

WS = "/api/v1/me/workspaces"
SHARED = "/api/v1/workspaces/shared"
CRYPTO = ("BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT")


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[str, Instrument]:
    return {symbol: await make_instrument(session, symbol) for symbol in CRYPTO}


@pytest.fixture
def make_headers(make_user):
    async def _make(email: str, role: UserRole = UserRole.trader, **kw) -> dict[str, str]:
        return bearer(create_access_token(await make_user(email, role=role, **kw)))

    return _make


@pytest.fixture
async def headers(make_headers) -> dict[str, str]:
    return await make_headers("trader@example.com")


def state_for(iid, **over) -> dict:
    state = {
        "layout": {"type": "1x1", "sizes": [1.0]},
        "sync": {"crosshair": True, "timeframe": False, "instrument": False},
        "panels": [
            {
                "id": "p1",
                "instrument_id": str(iid),
                "timeframe": "1h",
                "chart_type": "candles",
                "indicators": [
                    {"id": "i1", "name": "rsi", "params": {"length": 14}, "color": "#7E57C2"}
                ],
                "strategies": [{"id": "s1", "strategy_key": "ma_crossover", "params": {}}],
                "drawings": [
                    {
                        "id": "d1",
                        "type": "trendline",
                        "points": [
                            {"time": 1760000000, "price": 65000.5},
                            {"time": 1760003600, "price": 65500.0},
                        ],
                        "style": {"color": "#2196F3", "width": 1},
                    }
                ],
            }
        ],
        "watchlist": [str(iid)],
        "active_panel": "p1",
    }
    state.update(over)
    return state


def four_panels(seeded) -> dict:
    ids = [seeded[s].id for s in CRYPTO[:4]]
    state = state_for(ids[0])
    base = state["panels"][0]
    state["layout"] = {"type": "2x2", "sizes": [0.5, 0.5]}
    state["panels"] = []
    for n, iid in enumerate(ids):
        panel = copy.deepcopy(base)
        panel.update(id=f"p{n}", instrument_id=str(iid), indicators=[], strategies=[], drawings=[])
        state["panels"].append(panel)
    state["active_panel"] = "p0"
    return state


async def create(client, headers, name="W", **body) -> dict:
    res = await client.post(WS, json={"name": name, **body}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


async def put_state(client, headers, ws: dict, state: dict, version=None):
    version = ws["version"] if version is None else version
    return await client.put(
        f"{WS}/{ws['id']}", json={"state": state, "version": version}, headers=headers
    )


# --- default workspace, templates, limits, names -------------------------------------------


async def test_first_get_creates_the_default_workspace_once(
    client: AsyncClient, session: AsyncSession, seeded, headers
) -> None:
    res = await client.get(WS, headers=headers)
    assert res.status_code == 200
    (summary,) = res.json()
    assert summary["name"] == "Main" and summary["is_default"] is True
    assert (summary["position"], summary["version"], summary["panel_count"]) == (0, 1, 1)

    full = (await client.get(f"{WS}/{summary['id']}", headers=headers)).json()
    state = full["state"]
    assert state["layout"]["type"] == "1x1"
    panel = state["panels"][0]
    assert panel["instrument_id"] == str(seeded["BTC/USDT"].id)
    assert panel["instrument"]["symbol"] == "BTC/USDT" and panel["unavailable"] is False
    assert (panel["timeframe"], panel["chart_type"]) == ("1h", "candles")
    assert [(i["name"], i["params"]) for i in panel["indicators"]] == [
        ("ema", {"length": 20}),
        ("ema", {"length": 50}),
        ("rsi", {"length": 14}),
    ]
    assert state["watchlist"] == [str(seeded[s].id) for s in CRYPTO]

    assert len((await client.get(WS, headers=headers)).json()) == 1
    count = select(func.count()).select_from(Workspace).join(User, User.id == Workspace.user_id)
    assert await session.scalar(count.where(User.email == "trader@example.com")) == 1


async def test_default_template_without_seeded_instruments(client: AsyncClient, headers) -> None:
    (summary,) = (await client.get(WS, headers=headers)).json()
    state = (await client.get(f"{WS}/{summary['id']}", headers=headers)).json()["state"]
    assert state["panels"][0]["instrument_id"] is None
    assert state["panels"][0]["unavailable"] is False
    assert state["watchlist"] == []


async def test_templates(client: AsyncClient, seeded, headers) -> None:
    multi = await create(client, headers, "Grid", template="multi_chart")
    assert multi["state"]["layout"] == {"type": "2x2", "sizes": [0.5, 0.5]}
    assert [p["instrument"]["symbol"] for p in multi["state"]["panels"]] == list(CRYPTO[:4])
    assert all(p["timeframe"] == "1h" for p in multi["state"]["panels"])
    assert multi["is_default"] is True  # the user's first workspace

    blank = await create(client, headers, "Blank", template="blank")
    assert blank["state"]["panels"][0]["indicators"] == []
    assert blank["state"]["watchlist"] == [] and blank["is_default"] is False
    plain = await create(client, headers, "Plain")
    assert plain["state"]["panels"][0]["indicators"] == []  # neither state nor template: blank
    default = await create(client, headers, "Again", template="default")
    assert len(default["state"]["panels"][0]["indicators"]) == 3

    res = await client.post(
        WS,
        json={"name": "x", "template": "blank", "state": state_for(seeded["BTC/USDT"].id)},
        headers=headers,
    )
    assert res.status_code == 422
    res = await client.post(WS, json={"name": "x", "template": "fancy"}, headers=headers)
    assert res.status_code == 422


@pytest.mark.parametrize(("role", "limit"), [(UserRole.trader, 5), (UserRole.analyst, 20)])
async def test_role_limits(client: AsyncClient, make_headers, role, limit) -> None:
    headers = await make_headers(f"{role.value}@example.com", role)
    await client.get(WS, headers=headers)  # the default
    for n in range(limit - 1):
        await create(client, headers, f"W{n}")
    res = await client.post(WS, json={"name": "one too many"}, headers=headers)
    assert res.status_code == 400
    assert str(limit) in res.json()["detail"]


def test_role_limit_settings() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    assert [settings.workspace_limit(r.value) for r in UserRole] == [5, 20, 20, 20]


async def test_names_are_unique_case_insensitively(client: AsyncClient, headers) -> None:
    await create(client, headers, "Scalping")
    for name in ("Scalping", "scalping", "  SCALPING  "):
        res = await client.post(WS, json={"name": name}, headers=headers)
        assert res.status_code == 409, name
    other = await create(client, headers, "Swing")
    res = await client.patch(f"{WS}/{other['id']}", json={"name": "sCALPING"}, headers=headers)
    assert res.status_code == 409
    for bad in ("", "   ", "x" * 61):
        assert (await client.post(WS, json={"name": bad}, headers=headers)).status_code == 422


# --- state validation ------------------------------------------------------------------------

S = ["body", "state"]


def _set(path, value):
    def apply(state):
        target = state
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

    return apply


def _many(path, item, n):
    def apply(state):
        items = []
        for k in range(n):
            entry = copy.deepcopy(item)
            entry["id"] = f"x{k}"
            items.append(entry)
        _set(path, items)(state)

    return apply


DRAWING = {"id": "d", "type": "horizontal", "points": [{"time": 1, "price": 1.0}]}

CASES = [
    # (mutation, loc, message fragment)
    (_set(["layout", "type"], "1x2"), [*S, "panels"], "layout 1x2 needs 2 panel(s), got 1"),
    (_set(["layout", "type"], "3x3"), [*S, "layout", "type"], "Input should be"),
    (_set(["layout", "sizes"], [0.5, 0.5]), [*S, "layout", "sizes"], "needs 1 size(s), got 2"),
    (_set(["layout", "sizes"], [0.7]), [*S, "layout", "sizes"], "sizes must sum to 1, got 0.7"),
    (
        _set(["panels", 0, "indicators", 0, "id"], "p1"),
        [*S, "panels", 0, "indicators", 0, "id"],
        "duplicate id 'p1' (also used at state.panels[0].id)",
    ),
    (
        _set(["panels", 0, "drawings", 0, "id"], "s1"),
        [*S, "panels", 0, "drawings", 0, "id"],
        "duplicate id 's1'",
    ),
    (_set(["active_panel"], "p9"), [*S, "active_panel"], "no panel with id 'p9'"),
    (_set(["panels", 0, "timeframe"], "2h"), [*S, "panels", 0, "timeframe"], "Input should be"),
    (_set(["panels", 0, "chart_type"], "renko"), [*S, "panels", 0, "chart_type"], "Input"),
    (
        _set(["panels", 0, "indicators", 0, "name"], "nope"),
        [*S, "panels", 0, "indicators", 0, "name"],
        "unknown indicator 'nope'",
    ),
    (
        _set(["panels", 0, "indicators", 0, "params"], {"length": 0}),
        [*S, "panels", 0, "indicators", 0, "params"],
        "rsi: length must be between 1 and 1000, got 0",
    ),
    (
        _set(["panels", 0, "indicators", 0, "params"], {"lenght": 3}),
        [*S, "panels", 0, "indicators", 0, "params"],
        "lenght",
    ),
    (
        _set(["panels", 0, "strategies", 0, "strategy_key"], "nope"),
        [*S, "panels", 0, "strategies", 0, "strategy_key"],
        "nope",
    ),
    (
        _set(["panels", 0, "strategies", 0, "params"], {"fast": 30, "slow": 10}),
        [*S, "panels", 0, "strategies", 0, "params"],
        "fast",
    ),
    (
        _set(["panels", 0, "indicators", 0, "color"], "red"),
        [*S, "panels", 0, "indicators", 0, "color"],
        "String should match pattern",
    ),
    (
        _set(["panels", 0, "drawings", 0, "style", "color"], "#12345"),
        [*S, "panels", 0, "drawings", 0, "style", "color"],
        "pattern",
    ),
    (
        _set(["panels", 0, "drawings", 0, "points"], [{"time": 1, "price": 1.0}]),
        [*S, "panels", 0, "drawings", 0, "points"],
        "a trendline drawing needs 2 point(s), got 1",
    ),
    (
        _set(["panels", 0, "drawings", 0, "type"], "vertical"),
        [*S, "panels", 0, "drawings", 0, "points"],
        "a vertical drawing needs 1 point(s), got 2",
    ),
    (
        _set(["panels", 0, "drawings", 0], {**DRAWING, "type": "text"}),
        [*S, "panels", 0, "drawings", 0, "text"],
        "a text drawing needs a non-empty text",
    ),
    (
        _set(["panels", 0, "drawings", 0], {**DRAWING, "type": "text", "text": "x" * 201}),
        [*S, "panels", 0, "drawings", 0, "text"],
        "at most 200 characters",
    ),
    (
        _many(["panels", 0, "indicators"], {"name": "sma"}, 11),
        [*S, "panels", 0, "indicators"],
        "at most 10 items",
    ),
    (
        _many(["panels", 0, "strategies"], {"strategy_key": "rsi_reversal"}, 6),
        [*S, "panels", 0, "strategies"],
        "at most 5 items",
    ),
    (
        _many(["panels", 0, "drawings"], DRAWING, 201),
        [*S, "panels", 0, "drawings"],
        "at most 200 items",
    ),
    (_set(["panels", 0, "colour"], "#FFFFFF"), [*S, "panels", 0, "colour"], "Extra inputs"),
    (_set(["sync", "zoom"], True), [*S, "sync", "zoom"], "Extra inputs"),
    (
        _set(["panels", 0, "instrument_id"], str(uuid.UUID(int=1))),
        [*S, "panels", 0, "instrument_id"],
        f"unknown instrument {uuid.UUID(int=1)}",
    ),
]


@pytest.mark.parametrize(("mutate", "loc", "fragment"), CASES)
async def test_state_validation_reports_the_json_path(
    client: AsyncClient, seeded, headers, mutate, loc, fragment
) -> None:
    ws = await create(client, headers)
    state = state_for(seeded["BTC/USDT"].id)
    mutate(state)
    res = await put_state(client, headers, ws, state)
    assert res.status_code == 422, res.text
    errors = res.json()["detail"]
    match = [e for e in errors if e["loc"] == loc]
    assert match, errors
    assert fragment in match[0]["msg"], match[0]["msg"]
    # nothing was stored
    assert (await client.get(f"{WS}/{ws['id']}", headers=headers)).json()["version"] == 1


async def test_watchlist_rules(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    btc = str(seeded["BTC/USDT"].id)
    state = state_for(btc, watchlist=[btc, str(uuid.UUID(int=2)), btc])
    detail = (await put_state(client, headers, ws, state)).json()["detail"]
    assert {(tuple(e["loc"]), e["msg"]) for e in detail} == {
        (("body", "state", "watchlist", 1), f"unknown instrument {uuid.UUID(int=2)}"),
        (("body", "state", "watchlist", 2), f"duplicate instrument {btc}"),
    }
    state = state_for(btc, watchlist=[btc] * 51)
    res = await put_state(client, headers, ws, state)
    assert res.json()["detail"][0]["loc"] == ["body", "state", "watchlist"]


async def test_layout_sizes_and_panel_counts(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    state = four_panels(seeded)
    for layout, panels, sizes in (("1x2", 2, 2), ("2x1", 2, 2), ("1+2", 3, 2), ("2x2", 4, 2)):
        doc = copy.deepcopy(state)
        doc["panels"] = doc["panels"][:panels]
        doc["layout"] = {"type": layout, "sizes": [1 / sizes] * sizes}
        res = await put_state(client, headers, ws, doc)
        assert res.status_code == 200, (layout, res.text)
        ws = res.json()
    doc = copy.deepcopy(state)
    doc["layout"] = {"type": "2x2"}  # sizes omitted: equal parts
    assert (await put_state(client, headers, ws, doc)).status_code == 200


async def test_params_are_resolved_with_defaults(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    state = state_for(seeded["BTC/USDT"].id)
    state["panels"][0]["indicators"] = [{"id": "i1", "name": "macd"}]
    state["panels"][0]["strategies"] = [
        {"id": "s1", "strategy_key": "rsi_reversal", "params": {"oversold": 25}}
    ]
    res = await put_state(client, headers, ws, state)
    assert res.status_code == 200, res.text
    panel = res.json()["state"]["panels"][0]
    assert panel["indicators"][0]["params"] == {"fast": 12, "slow": 26, "signal": 9}
    assert panel["indicators"][0]["visible"] is True and panel["indicators"][0]["color"] is None
    assert panel["strategies"][0]["params"] == {"length": 14, "oversold": 25.0, "overbought": 70.0}


async def test_state_size_limit(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    state = four_panels(seeded)
    points = [{"time": 1760000000, "price": 65000.123456}, {"time": 1760003600, "price": 1.5}]
    for panel in state["panels"]:
        panel["drawings"] = [
            {
                "id": f"{panel['id']}-{k}".ljust(40, "x"),
                "type": "trendline",
                "points": points,
                "text": "x" * 200,
            }
            for k in range(200)
        ]
    assert len(json.dumps(state)) > 256 * 1024
    res = await put_state(client, headers, ws, state)
    assert res.status_code == 422
    (err,) = res.json()["detail"]
    assert err["loc"] == ["body", "state"]
    assert "at most 262144" in err["msg"]


async def test_a_read_can_be_sent_back_as_is(client: AsyncClient, seeded, headers) -> None:
    """The read-only panel fields (instrument, unavailable) are accepted and ignored."""
    ws = await create(client, headers, template="default")
    res = await put_state(client, headers, ws, ws["state"])
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2
    row_state = res.json()["state"]
    assert row_state["panels"][0]["instrument"]["symbol"] == "BTC/USDT"


# --- versions --------------------------------------------------------------------------------


async def test_stale_version_is_409_with_the_current_version(
    client: AsyncClient, seeded, headers
) -> None:
    ws = await create(client, headers)
    state = state_for(seeded["BTC/USDT"].id)
    res = await put_state(client, headers, ws, state)
    assert res.status_code == 200 and res.json()["version"] == 2
    assert res.headers["etag"] == '"2"'

    res = await put_state(client, headers, ws, state, version=1)  # the other device
    assert res.status_code == 409
    body = res.json()
    assert body["current_version"] == 2
    assert body["updated_at"] and "reload" in body["detail"]
    assert res.headers["etag"] == '"2"'


async def test_if_match_header(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    state = state_for(seeded["BTC/USDT"].id)
    path = f"{WS}/{ws['id']}"
    res = await client.put(path, json={"state": state}, headers={**headers, "If-Match": '"1"'})
    assert res.status_code == 200 and res.json()["version"] == 2
    res = await client.put(path, json={"state": state}, headers={**headers, "If-Match": 'W/"2"'})
    assert res.status_code == 200 and res.json()["version"] == 3
    res = await client.put(path, json={"state": state}, headers={**headers, "If-Match": "2"})
    assert res.status_code == 409
    res = await client.put(path, json={"state": state}, headers=headers)
    assert res.status_code == 428
    res = await client.put(
        path, json={"state": state, "version": 3}, headers={**headers, "If-Match": "2"}
    )
    assert res.status_code == 422  # disagree
    res = await client.put(path, json={"state": state}, headers={**headers, "If-Match": "x"})
    assert res.status_code == 422
    assert (await client.get(path, headers=headers)).headers["etag"] == '"3"'


async def test_patch_with_a_stale_version_is_409(client: AsyncClient, seeded, headers) -> None:
    ws = await create(client, headers)
    await put_state(client, headers, ws, state_for(seeded["BTC/USDT"].id))
    res = await client.patch(f"{WS}/{ws['id']}", json={"name": "x", "version": 1}, headers=headers)
    assert res.status_code == 409 and res.json()["current_version"] == 2
    res = await client.patch(f"{WS}/{ws['id']}", json={"name": "x", "version": 2}, headers=headers)
    assert res.status_code == 200
    assert res.json()["version"] == 2  # renaming is not a state change


# --- default, order, duplicate, delete -----------------------------------------------------


async def _defaults(session: AsyncSession, email: str = "trader@example.com") -> list[str]:
    """Names of the user's default workspaces (scoped: other tests may commit workspaces)."""
    session.expire_all()
    return list(
        await session.scalars(
            select(Workspace.name)
            .join(User, User.id == Workspace.user_id)
            .where(Workspace.is_default, User.email == email)
        )
    )


async def test_switching_the_default(client: AsyncClient, session: AsyncSession, headers) -> None:
    (main,) = (await client.get(WS, headers=headers)).json()
    other = await create(client, headers, "Other")
    res = await client.patch(f"{WS}/{other['id']}", json={"is_default": True}, headers=headers)
    assert res.status_code == 200 and res.json()["is_default"] is True
    assert await _defaults(session) == ["Other"]
    listed = {w["name"]: w["is_default"] for w in (await client.get(WS, headers=headers)).json()}
    assert listed == {"Main": False, "Other": True}
    res = await client.patch(f"{WS}/{main['id']}", json={"is_default": False}, headers=headers)
    assert res.status_code == 422  # unset by choosing another default


async def test_partial_unique_index_allows_one_default(session: AsyncSession, make_user) -> None:
    user = await make_user("t@example.com")
    for n in range(2):
        session.add(
            Workspace(
                user_id=user.id, name=f"w{n}", position=n, is_default=True, state={"panels": []}
            )
        )
    with pytest.raises(IntegrityError, match="uq_workspaces_default"):
        await session.commit()


async def test_deleting_the_default_promotes_the_first_remaining(
    client: AsyncClient, session: AsyncSession, headers
) -> None:
    (main,) = (await client.get(WS, headers=headers)).json()
    a = await create(client, headers, "A")
    b = await create(client, headers, "B")
    await client.put(f"{WS}/order", json={"ids": [main["id"], b["id"], a["id"]]}, headers=headers)
    assert (await client.delete(f"{WS}/{main['id']}", headers=headers)).status_code == 204
    assert await _defaults(session) == ["B"]
    assert (await client.get(f"{WS}/{main['id']}", headers=headers)).status_code == 404


async def test_deleting_the_last_one_recreates_the_default_on_next_get(
    client: AsyncClient, headers
) -> None:
    (main,) = (await client.get(WS, headers=headers)).json()
    assert (await client.delete(f"{WS}/{main['id']}", headers=headers)).status_code == 204
    (again,) = (await client.get(WS, headers=headers)).json()
    assert again["id"] != main["id"] and again["is_default"] is True and again["name"] == "Main"


async def test_reorder_requires_exactly_the_users_ids(
    client: AsyncClient, headers, make_headers
) -> None:
    (main,) = (await client.get(WS, headers=headers)).json()
    a, b = await create(client, headers, "A"), await create(client, headers, "B")
    others = await make_headers("other@example.com")
    (foreign,) = (await client.get(WS, headers=others)).json()
    bad = [
        [main["id"], a["id"]],
        [main["id"], a["id"], b["id"], a["id"]],
        [main["id"], a["id"], foreign["id"]],
        [main["id"], a["id"], b["id"], foreign["id"]],
        [],
    ]
    for ids in bad:
        res = await client.put(f"{WS}/order", json={"ids": ids}, headers=headers)
        assert res.status_code == 422, ids
    res = await client.put(
        f"{WS}/order", json={"ids": [b["id"], main["id"], a["id"]]}, headers=headers
    )
    assert res.status_code == 200
    assert [(w["name"], w["position"]) for w in res.json()] == [("B", 0), ("Main", 1), ("A", 2)]
    listed = (await client.get(WS, headers=headers)).json()
    assert [w["name"] for w in listed] == ["B", "Main", "A"]


async def test_duplicate(client: AsyncClient, seeded, make_headers) -> None:
    headers = await make_headers("analyst@example.com", UserRole.analyst)
    ws = await create(client, headers, "Setup", template="default")
    await client.post(f"{WS}/{ws['id']}/share", headers=headers)
    first = await client.post(f"{WS}/{ws['id']}/duplicate", headers=headers)
    assert first.status_code == 201
    copy1 = first.json()
    assert copy1["name"] == "Setup (copy)"
    assert copy1["is_default"] is False and copy1["is_shared"] is False
    assert copy1["share_slug"] is None and copy1["version"] == 1
    assert copy1["state"] == ws["state"]
    copy2 = (await client.post(f"{WS}/{ws['id']}/duplicate", headers=headers)).json()
    assert copy2["name"] == "Setup (copy 2)"
    long = await create(client, headers, "L" * 60)
    copy3 = (await client.post(f"{WS}/{long['id']}/duplicate", headers=headers)).json()
    assert copy3["name"] == "L" * 53 + " (copy)" and len(copy3["name"]) == 60


# --- instruments that went away ------------------------------------------------------------


async def test_inactive_and_deleted_instruments_are_flagged_but_load(
    client: AsyncClient, session: AsyncSession, seeded, headers
) -> None:
    ws = await create(client, headers, template="multi_chart")
    eth, bnb = seeded["ETH/USDT"], seeded["BNB/USDT"]
    eth.is_active = False
    await session.commit()
    await session.execute(delete(Instrument).where(Instrument.id == bnb.id))
    await session.commit()

    res = await client.get(f"{WS}/{ws['id']}", headers=headers)
    assert res.status_code == 200
    body = res.json()
    flags = {p["id"]: (p["unavailable"], p["instrument"]) for p in body["state"]["panels"]}
    assert flags["p1"][0] is False
    assert flags["p2"][0] is True and flags["p2"][1]["is_active"] is False
    assert flags["p3"] == (True, None)
    assert set(body["unavailable_instrument_ids"]) == {str(eth.id), str(bnb.id)}

    # saving it back keeps working: the deleted instrument was already in the workspace
    res = await put_state(client, headers, body, body["state"])
    assert res.status_code == 200, res.text
    # but a deleted instrument cannot be newly added
    other = await create(client, headers, "Other")
    state = state_for(seeded["BTC/USDT"].id, watchlist=[str(bnb.id)])
    res = await put_state(client, headers, other, state)
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "state", "watchlist", 0]


# --- sharing ---------------------------------------------------------------------------------


async def test_sharing(client: AsyncClient, session: AsyncSession, seeded, make_headers) -> None:
    trader = await make_headers("trader@example.com")
    (trader_ws,) = (await client.get(WS, headers=trader)).json()
    res = await client.post(f"{WS}/{trader_ws['id']}/share", headers=trader)
    assert res.status_code == 403

    owner = await make_user_with_name(session, "expert@example.com", "Rania K.", UserRole.expert)
    expert = bearer(create_access_token(owner))
    ws = await create(client, expert, "Breakouts", template="default")
    res = await client.post(f"{WS}/{ws['id']}/share", headers=expert)
    assert res.status_code == 200
    slug = res.json()["share_slug"]
    assert res.json()["is_shared"] is True and len(slug) == 16
    again = await client.post(f"{WS}/{ws['id']}/share", headers=expert)
    assert again.json()["share_slug"] == slug  # idempotent

    res = await client.get(f"{SHARED}/{slug}", headers=trader)
    assert res.status_code == 200
    shared = res.json()
    assert shared["name"] == "Breakouts"
    assert shared["owner"] == {"display_name": "Rania K.", "role": "expert"}
    assert shared["state"]["panels"][0]["instrument"]["symbol"] == "BTC/USDT"
    text = res.text
    assert str(owner.id) not in text and ws["id"] not in text
    assert "user_id" not in text and "expert@example.com" not in text

    res = await client.post(f"{SHARED}/{slug}/import", headers=trader)
    assert res.status_code == 201
    imported = res.json()
    assert imported["name"] == "Breakouts" and imported["state"] == ws["state"]
    assert imported["is_shared"] is False and imported["is_default"] is False
    res = await client.post(f"{SHARED}/{slug}/import", headers=trader)
    assert res.json()["name"] == "Breakouts (copy)"
    res = await client.post(f"{SHARED}/{slug}/import", json={"name": "Mine"}, headers=trader)
    assert res.json()["name"] == "Mine"
    res = await client.post(f"{SHARED}/{slug}/import", json={"name": "mine"}, headers=trader)
    assert res.status_code == 409

    res = await client.delete(f"{WS}/{ws['id']}/share", headers=expert)
    assert res.json() == {"is_shared": False, "share_slug": None}
    assert (await client.get(f"{SHARED}/{slug}", headers=trader)).status_code == 404
    assert (await client.post(f"{SHARED}/{slug}/import", headers=trader)).status_code == 404
    assert (await client.get(f"{SHARED}/nope", headers=trader)).status_code == 404


async def test_import_respects_the_limit(client: AsyncClient, seeded, make_headers) -> None:
    analyst = await make_headers("analyst@example.com", UserRole.analyst)
    ws = await create(client, analyst, "Shared")
    slug = (await client.post(f"{WS}/{ws['id']}/share", headers=analyst)).json()["share_slug"]
    trader = await make_headers("trader@example.com")
    for n in range(5):
        await create(client, trader, f"W{n}")
    res = await client.post(f"{SHARED}/{slug}/import", headers=trader)
    assert res.status_code == 400


async def make_user_with_name(session: AsyncSession, email: str, name: str, role: UserRole):
    user = User(
        email=email, hashed_password=hash_password(DEFAULT_PASSWORD), role=role, full_name=name
    )
    session.add(user)
    await session.commit()
    return user


# --- access ----------------------------------------------------------------------------------


async def test_other_users_workspaces_are_404(client: AsyncClient, seeded, make_headers) -> None:
    owner = await make_headers("analyst@example.com", UserRole.analyst)
    ws = await create(client, owner, "Private")
    intruder = await make_headers("intruder@example.com", UserRole.admin)
    path = f"{WS}/{ws['id']}"
    state = state_for(seeded["BTC/USDT"].id)
    requests = [
        ("GET", path, None),
        ("PUT", path, {"state": state, "version": 1}),
        ("PATCH", path, {"name": "mine now"}),
        ("POST", f"{path}/duplicate", None),
        ("POST", f"{path}/share", None),
        ("DELETE", f"{path}/share", None),
        ("DELETE", path, None),
        ("GET", f"{WS}/{uuid.uuid4()}", None),
    ]
    for method, url, body in requests:
        res = await client.request(method, url, json=body, headers=intruder)
        assert res.status_code == 404, (method, url, res.status_code)
    assert (await client.get(path, headers=owner)).json()["name"] == "Private"


async def test_api_keys_are_refused_and_auth_is_required(client: AsyncClient, headers) -> None:
    created = await create_key(client, headers, ["market:read", "stream"])
    (ws,) = (await client.get(WS, headers=headers)).json()
    for method, url in (
        ("GET", WS),
        ("POST", WS),
        ("GET", f"{WS}/{ws['id']}"),
        ("PUT", f"{WS}/order"),
        ("GET", f"{SHARED}/anything"),
    ):
        res = await client.request(method, url, json={}, headers=xkey(created["key"]))
        assert res.status_code == 403, url
        assert (await client.request(method, url, json={})).status_code == 401, url


# --- WebSocket -------------------------------------------------------------------------------


async def _next_update(ws) -> dict:
    return await recv_until(ws, lambda m: m["type"] == "workspace_updated")


async def test_workspace_updated_reaches_only_the_owner(
    client: AsyncClient, hub: WebSocketHub, seeded, make_user
) -> None:
    owner = await make_user("analyst@example.com", role=UserRole.analyst)
    other = await make_user("other@example.com")
    headers = bearer(create_access_token(owner))
    async with (
        ws_connect(create_access_token(owner)) as mine,
        ws_connect(create_access_token(other)) as theirs,
    ):
        (main,) = (await client.get(WS, headers=headers)).json()
        msg = await _next_update(mine)
        assert msg == {
            "type": "workspace_updated",
            "workspace_id": main["id"],
            "version": 1,
            "action": "created",
            "topic": f"user:{owner.id}",
            "sent_at": msg["sent_at"],
        }

        b = await create(client, headers, "B")
        assert (await _next_update(mine))["action"] == "created"
        await put_state(client, headers, b, state_for(seeded["BTC/USDT"].id))
        msg = await _next_update(mine)
        assert (msg["action"], msg["workspace_id"], msg["version"]) == (
            "state_updated",
            b["id"],
            2,
        )
        await client.patch(
            f"{WS}/{b['id']}", json={"name": "B2", "is_default": True}, headers=headers
        )
        assert [(await _next_update(mine))["action"] for _ in range(2)] == [
            "renamed",
            "default_changed",
        ]
        await client.put(f"{WS}/order", json={"ids": [b["id"], main["id"]]}, headers=headers)
        msg = await _next_update(mine)
        assert (msg["action"], msg["workspace_id"], msg["version"]) == ("reordered", None, None)
        dup = (await client.post(f"{WS}/{b['id']}/duplicate", headers=headers)).json()
        msg = await _next_update(mine)
        assert (msg["action"], msg["workspace_id"]) == ("created", dup["id"])
        await client.post(f"{WS}/{b['id']}/share", headers=headers)
        assert (await _next_update(mine))["action"] == "shared"
        await client.delete(f"{WS}/{b['id']}/share", headers=headers)
        assert (await _next_update(mine))["action"] == "unshared"
        await client.delete(f"{WS}/{b['id']}", headers=headers)  # the default
        msg = await _next_update(mine)
        assert (msg["action"], msg["workspace_id"], msg["version"]) == ("deleted", b["id"], None)
        msg = await _next_update(mine)
        assert (msg["action"], msg["workspace_id"]) == ("default_changed", main["id"])

        # the other user's socket got none of it
        await theirs.send_text(json.dumps({"op": "ping"}))
        while (msg := await recv(theirs)) and msg["type"] != "pong":
            assert msg["type"] != "workspace_updated", msg


async def test_publish_failure_does_not_fail_the_request(
    client: AsyncClient, headers, monkeypatch
) -> None:
    from app.realtime import publisher

    async def broken(*_args, **_kw):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(publisher, "publish", broken)
    assert (await client.get(WS, headers=headers)).status_code == 200
    assert (await client.post(WS, json={"name": "x"}, headers=headers)).status_code == 201


# --- real concurrency (committed data, separate connections) ------------------------------


@pytest.fixture
async def real_client(migrated_db: str) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker]]:
    """The app on a real connection pool: every request has its own connection and commits for
    real, so concurrent requests race in Postgres. Cleans up its users afterwards."""
    engine = create_async_engine(migrated_db, pool_size=5)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            c.emails = emails
            yield c, factory
    finally:
        app.dependency_overrides.clear()
        async with factory() as s:
            await s.execute(delete(User).where(User.email.in_(emails)))
            await s.commit()
        await engine.dispose()


async def _real_user(real_client) -> dict[str, str]:
    client, factory = real_client
    email = f"race-{uuid.uuid4().hex[:8]}@example.com"
    client.emails.append(email)
    async with factory() as s:
        user = User(email=email, hashed_password="x", role=UserRole.trader)
        s.add(user)
        await s.commit()
        return bearer(create_access_token(user))


async def test_concurrent_first_gets_create_one_default(real_client) -> None:
    client, factory = real_client
    headers = await _real_user(real_client)
    results = await asyncio.gather(*(client.get(WS, headers=headers) for _ in range(4)))
    assert [r.status_code for r in results] == [200] * 4, [r.text for r in results]
    ids = {tuple(w["id"] for w in r.json()) for r in results}
    assert len(ids) == 1 and len(next(iter(ids))) == 1, [r.json() for r in results]


async def test_concurrent_puts_with_the_same_version(real_client) -> None:
    client, factory = real_client
    headers = await _real_user(real_client)
    (ws,) = (await client.get(WS, headers=headers)).json()
    full = (await client.get(f"{WS}/{ws['id']}", headers=headers)).json()
    a, b = copy.deepcopy(full["state"]), copy.deepcopy(full["state"])
    a["panels"][0]["timeframe"], b["panels"][0]["timeframe"] = "4h", "15m"
    results = await asyncio.gather(
        put_state(client, headers, full, a, version=1),
        put_state(client, headers, full, b, version=1),
    )
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
    winner = next(r for r in results if r.status_code == 200).json()
    loser = next(r for r in results if r.status_code == 409).json()
    assert winner["version"] == 2 and loser["current_version"] == 2
    stored = (await client.get(f"{WS}/{ws['id']}", headers=headers)).json()
    assert stored["version"] == 2
    assert stored["state"]["panels"][0]["timeframe"] == winner["state"]["panels"][0]["timeframe"]


async def test_concurrent_creates_respect_the_limit(real_client) -> None:
    client, _ = real_client
    headers = await _real_user(real_client)
    await client.get(WS, headers=headers)  # 1 of 5
    results = await asyncio.gather(
        *(client.post(WS, json={"name": f"W{n}"}, headers=headers) for n in range(8))
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [201] * 4 + [400] * 4, [(r.status_code, r.text[:200]) for r in results]
    listed = (await client.get(WS, headers=headers)).json()
    assert sorted(w["position"] for w in listed) == [0, 1, 2, 3, 4], listed


def test_exported_json_schema_is_up_to_date() -> None:
    from pathlib import Path

    from app.schemas.workspaces import state_json_schema

    path = Path(__file__).resolve().parents[2] / "docs" / "workspace-state.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == state_json_schema(), (
        "regenerate: python -m app.schemas.workspaces > ../docs/workspace-state.schema.json"
    )
