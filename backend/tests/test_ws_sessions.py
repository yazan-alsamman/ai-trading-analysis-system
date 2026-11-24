"""B12 part 2: login sessions and WebSockets. Logout closes that session's sockets only; a
password change, a refresh-token reuse or a purge closes every login socket of the user (API-key
sockets stay on a password change); a rotation keeps the session; an older token without a
session id closes on the user-wide events; a lost event is caught by the heartbeat re-check.

Real sessions on their own pool (``committed_session_factory``), as in test_ws_reauth.py: the
re-checks of several sockets run while the request that sent the event still uses its own."""

import asyncio
import uuid

import jwt
import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token, decode_token
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.realtime import auth_events
from app.realtime.hub import HubConfig, WebSocketHub
from app.services import purge
from tests.api_key_utils import create_key
from tests.test_ws_reauth import api_key_query, assert_open, revoked_message
from tests.utils import DEFAULT_PASSWORD, bearer
from tests.ws_utils import ws_connect

SLOW = HubConfig(heartbeat_seconds=60, idle_timeout_seconds=120)  # only the event can be fast
FAST = HubConfig(heartbeat_seconds=0.3, idle_timeout_seconds=30)
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
PASSWORD = "/api/v1/users/me/password"
ENDED = ("auth_revoked", 4401, "session ended")


@pytest.fixture
def session_factory(
    committed_session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    return committed_session_factory


async def login(client: AsyncClient, email: str) -> dict:
    res = await client.post(LOGIN, json={"email": email, "password": DEFAULT_PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()


def sid(pair: dict) -> uuid.UUID:
    return decode_token(pair["access_token"], "access")["sid"]


async def closed_as(ws) -> tuple[str, int, str]:
    message, code, reason = await revoked_message(ws)
    return message["code"], code, reason


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_logout_closes_only_that_session(
    client: AsyncClient, hub: WebSocketHub, make_user
) -> None:
    await make_user("phone@example.com")
    phone, laptop = (
        await login(client, "phone@example.com"),
        await login(client, "phone@example.com"),
    )
    assert sid(phone) != sid(laptop)
    async with (
        ws_connect(phone["access_token"]) as on_phone,
        ws_connect(laptop["access_token"]) as on_laptop,
    ):
        await assert_open(on_phone)
        await assert_open(on_laptop)
        started = asyncio.get_running_loop().time()
        res = await client.post(
            LOGOUT,
            json={"refresh_token": phone["refresh_token"]},
            headers=bearer(phone["access_token"]),
        )
        assert res.status_code == 204
        assert await closed_as(on_phone) == ENDED
        assert asyncio.get_running_loop().time() - started < 2  # the event, not the heartbeat
        await assert_open(on_laptop)  # the other device's session stays
    # REST is unchanged: the access token stays valid until it expires (stateless JWT)
    me = await client.get("/api/v1/users/me", headers=bearer(phone["access_token"]))
    assert me.status_code == 200
    # but a new socket with the logged-out session is refused
    async with ws_connect(phone["access_token"]) as again:
        with pytest.raises(WebSocketDisconnect) as refused:
            await again.receive_text(timeout=3)
    assert (refused.value.code, refused.value.reason) == (4401, "session ended")


async def test_logout_revokes_the_whole_family(
    client: AsyncClient, session: AsyncSession, make_user
) -> None:
    """A logged-out session cannot be refreshed from an older sibling either."""
    user = await make_user("family@example.com")
    first = await login(client, "family@example.com")
    rotated = (await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})).json()
    assert sid(rotated) == sid(first)
    res = await client.post(
        LOGOUT,
        json={"refresh_token": rotated["refresh_token"]},
        headers=bearer(rotated["access_token"]),
    )
    assert res.status_code == 204
    rows = (
        await session.scalars(
            select(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert len(rows) == 2 and {r.family_id for r in rows} == {sid(first)}
    assert all(r.revoked_at is not None for r in rows)


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_rotation_keeps_the_session_and_the_socket(
    client: AsyncClient, hub: WebSocketHub, make_user
) -> None:
    await make_user("rotate@example.com")
    pair = await login(client, "rotate@example.com")
    async with ws_connect(pair["access_token"]) as ws:
        for _ in range(2):
            res = await client.post(REFRESH, json={"refresh_token": pair["refresh_token"]})
            assert res.status_code == 200
            new = res.json()
            assert sid(new) == sid(pair)
            pair = new
        [client_] = hub._clients
        client_.recheck.set()  # a re-check now: the family still has a live row
        await asyncio.sleep(0.2)
        await assert_open(ws)


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_password_change_closes_every_login_socket_not_api_keys(
    client: AsyncClient, hub: WebSocketHub, make_user
) -> None:
    await make_user("pw-ws@example.com")
    one, two = await login(client, "pw-ws@example.com"), await login(client, "pw-ws@example.com")
    key = await create_key(client, bearer(one["access_token"]), ["stream"])
    async with (
        ws_connect(one["access_token"]) as first,
        ws_connect(two["access_token"]) as second,
        ws_connect(None, query=api_key_query(key)) as by_key,
    ):
        for ws in (first, second, by_key):
            await assert_open(ws)
        res = await client.post(
            PASSWORD,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "NewPassw0rd9"},
            headers=bearer(one["access_token"]),
        )
        assert res.status_code == 204
        assert await closed_as(first) == ENDED
        assert await closed_as(second) == ENDED
        await assert_open(by_key)  # changing the password does not revoke API keys
        # a new login after the change has its own session: it connects
        res = await client.post(
            LOGIN, json={"email": "pw-ws@example.com", "password": "NewPassw0rd9"}
        )
        async with ws_connect(res.json()["access_token"]) as fresh:
            await assert_open(fresh)


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_refresh_reuse_closes_every_login_socket(
    client: AsyncClient, hub: WebSocketHub, make_user
) -> None:
    await make_user("reuse@example.com")
    stolen, other = (
        await login(client, "reuse@example.com"),
        await login(client, "reuse@example.com"),
    )
    async with (
        ws_connect(stolen["access_token"]) as first,
        ws_connect(other["access_token"]) as second,
    ):
        await assert_open(first)
        res = await client.post(REFRESH, json={"refresh_token": stolen["refresh_token"]})
        assert res.status_code == 200
        reused = await client.post(REFRESH, json={"refresh_token": stolen["refresh_token"]})
        assert reused.status_code == 401
        assert await closed_as(first) == ENDED
        assert await closed_as(second) == ENDED


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_purge_demo_closes_the_socket(
    client: AsyncClient,
    hub: WebSocketHub,
    make_user,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await make_user("demo-ws@example.com")
    pair = await login(client, "demo-ws@example.com")
    async with ws_connect(pair["access_token"]) as ws:
        await assert_open(ws)
        report = await purge.purge_demo(session_factory, "demo-ws", execute=True)
        assert report.deleted and report.users == [("demo-ws@example.com", "trader")]
        assert await closed_as(ws) == ("auth_revoked", 4401, "user not found")


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_an_old_token_without_sid_closes_on_user_wide_events(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, make_user
) -> None:
    user = await make_user("legacy@example.com")
    legacy = create_access_token(user)  # issued before the deploy: no sid
    assert "sid" not in jwt.decode(legacy, options={"verify_signature": False})
    pair = await login(client, "legacy@example.com")
    async with ws_connect(legacy) as ws:
        await assert_open(ws)
        [client_] = hub._clients
        assert client_.session_id is None
        # a logout of a session is not a user-wide event: the old socket stays
        res = await client.post(
            LOGOUT,
            json={"refresh_token": pair["refresh_token"]},
            headers=bearer(pair["access_token"]),
        )
        assert res.status_code == 204
        client_.recheck.set()
        await asyncio.sleep(0.2)
        await assert_open(ws)
        # a password change ends every session, the old token's too
        await asyncio.sleep(1.05)  # iat is in whole seconds: the change must come after it
        res = await client.post(
            PASSWORD,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "NewPassw0rd9"},
            headers=bearer(legacy),
        )
        assert res.status_code == 204
        assert await closed_as(ws) == ENDED
    stored = await session.get(User, user.id, populate_existing=True)
    assert stored.sessions_revoked_at is not None


@pytest.mark.parametrize("hub_config", [FAST])
async def test_a_lost_event_is_caught_by_the_heartbeat(
    client: AsyncClient, hub: WebSocketHub, make_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    await make_user("lost@example.com")
    pair = await login(client, "lost@example.com")
    published = []

    async def lost(**kw) -> None:  # Redis lost the event: only the heartbeat re-check is left
        published.append(kw)

    monkeypatch.setattr(auth_events, "publish", lost)
    async with ws_connect(pair["access_token"]) as ws:
        await assert_open(ws)
        started = asyncio.get_running_loop().time()
        res = await client.post(
            LOGOUT,
            json={"refresh_token": pair["refresh_token"]},
            headers=bearer(pair["access_token"]),
        )
        assert res.status_code == 204
        assert await closed_as(ws) == ENDED
        assert asyncio.get_running_loop().time() - started <= FAST.heartbeat_seconds + 0.5
    assert published == [{"session_id": sid(pair)}]


async def test_session_event_wakes_only_that_session(hub: WebSocketHub) -> None:
    from tests.test_ws_hub import FakeWebSocket  # noqa: PLC0415

    user, session_a, session_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    a = hub.new_client(FakeWebSocket(), user, session_id=session_a)
    b = hub.new_client(FakeWebSocket(), user, session_id=session_b)
    legacy = hub.new_client(FakeWebSocket(), user)
    for c in (a, b, legacy):
        await hub.register(c)
    assert hub.auth_changed(f'{{"session_id": "{session_a}"}}') == 1
    assert a.recheck.is_set() and not b.recheck.is_set() and not legacy.recheck.is_set()
    assert hub.auth_changed(f'{{"user_id": "{user}"}}') == 3


def test_access_tokens_carry_the_session() -> None:
    user = User(id=uuid.uuid4(), email="x@example.com", hashed_password="x", role=UserRole.trader)
    session_id = uuid.uuid4()
    assert decode_token(create_access_token(user, session_id), "access")["sid"] == session_id
    assert decode_token(create_access_token(user), "access")["sid"] is None
