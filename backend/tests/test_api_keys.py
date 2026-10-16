"""API keys: lifecycle, authentication, scopes, where keys are refused, last_used_at, admin
endpoints, usage counters and the housekeeping cleanup."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import MAX_KEYS_PER_ROLE, ApiKey
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services import api_key_service, housekeeping
from app.tasks import celery_app
from app.tasks import housekeeping as housekeeping_tasks
from tests.api_key_utils import KEYS, create_key, unreachable_redis, xkey
from tests.market_utils import make_instrument
from tests.utils import bearer

INSTRUMENTS = "/api/v1/market/instruments"
ALL = ["market:read", "indicators:read", "strategies:read", "signals:read", "stream"]


@pytest.fixture
async def other_headers(make_user, login) -> dict[str, str]:
    await make_user("other@example.com")
    return bearer((await login("other@example.com"))["access_token"])


async def _row(session: AsyncSession, key_id: str) -> ApiKey:
    session.expire_all()
    return await session.get(ApiKey, uuid.UUID(key_id))


# --- lifecycle --------------------------------------------------------------------------------


async def test_create_returns_key_once_and_stores_only_its_hash(
    client: AsyncClient, session: AsyncSession, trader_headers
) -> None:
    created = await create_key(client, trader_headers, ["signals:read", "market:read"])
    key = created["key"]
    assert key.startswith(f"tk_{created['prefix']}_") and len(created["prefix"]) == 8
    assert len(key) > 50
    assert created["scopes"] == ["market:read", "signals:read"]
    assert created["revoked"] is False and created["rate_limit_per_minute"] is None

    row = await _row(session, created["id"])
    assert row.key_hash == hashlib.sha256(key.encode()).hexdigest()
    assert row.key_hash != key and key not in row.key_hash

    listed = (await client.get(KEYS, headers=trader_headers)).json()
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0] and "key_hash" not in listed[0]
    assert key not in str(listed) and row.key_hash not in str(listed)

    res = await client.get(INSTRUMENTS, headers=xkey(key))
    assert res.status_code == 200, res.text


@pytest.mark.parametrize(
    "bad",
    ["garbage", "tk_short_secret", "tk_abcdefgh_wrongsecret", "Bearer x", "tk_abcdefgh_"],
)
async def test_unknown_or_malformed_key_is_401(client: AsyncClient, trader_headers, bad) -> None:
    await create_key(client, trader_headers)
    res = await client.get(INSTRUMENTS, headers=xkey(bad))
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid API key"


async def test_wrong_secret_with_a_real_prefix_is_401(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers)
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"][:-2] + "zz"))
    assert res.status_code == 401


async def test_revoked_key_is_401(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers)
    assert (
        await client.delete(f"{KEYS}/{created['id']}", headers=trader_headers)
    ).status_code == 204
    # idempotent
    assert (
        await client.delete(f"{KEYS}/{created['id']}", headers=trader_headers)
    ).status_code == 204
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    assert res.status_code == 401
    assert res.json()["detail"] == "API key has been revoked"
    listed = (await client.get(KEYS, headers=trader_headers)).json()
    assert listed[0]["revoked"] is True and listed[0]["revoked_at"] is not None


async def test_expired_key_is_401(client: AsyncClient, session: AsyncSession, trader_headers):
    created = await create_key(client, trader_headers, expires_in_days=30)
    expires = datetime.fromisoformat(created["expires_at"])
    assert timedelta(days=29, hours=23) < expires - datetime.now(UTC) <= timedelta(days=30)
    row = await _row(session, created["id"])
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    assert res.status_code == 401
    assert res.json()["detail"] == "API key has expired"


async def test_inactive_owner_is_403(client: AsyncClient, session: AsyncSession, trader_headers):
    created = await create_key(client, trader_headers)
    user = await session.scalar(select(User).where(User.email == "trader@example.com"))
    user.is_active = False
    await session.commit()
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    assert res.status_code == 403
    assert res.json()["detail"] == "Inactive user"


@pytest.mark.parametrize("role", list(UserRole))
async def test_max_keys_per_role(client: AsyncClient, make_user, login, role: UserRole) -> None:
    await make_user(f"{role.value}@example.com", role=role)
    headers = bearer((await login(f"{role.value}@example.com"))["access_token"])
    maximum = MAX_KEYS_PER_ROLE[role]
    assert maximum == {"trader": 2, "analyst": 5, "expert": 5, "admin": 10}[role.value]
    created = [await create_key(client, headers, name=f"k{i}") for i in range(maximum)]
    res = await client.post(KEYS, json={"name": "one more", "scopes": ["stream"]}, headers=headers)
    assert res.status_code == 400
    assert str(maximum) in res.json()["detail"]
    # a revoked key frees its slot
    await client.delete(f"{KEYS}/{created[0]['id']}", headers=headers)
    await create_key(client, headers, name="replacement")


async def test_patch_name_scopes_and_limit(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers, ["market:read"])
    key = created["key"]
    assert (await client.get("/api/v1/signals", headers=xkey(key))).status_code == 403

    res = await client.patch(
        f"{KEYS}/{created['id']}",
        json={"name": "renamed", "scopes": ["signals:read", "signals:read"]},
        headers=trader_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "renamed" and res.json()["scopes"] == ["signals:read"]
    assert (await client.get("/api/v1/signals", headers=xkey(key))).status_code == 200
    assert (await client.get(INSTRUMENTS, headers=xkey(key))).status_code == 403

    res = await client.patch(
        f"{KEYS}/{created['id']}", json={"rate_limit_per_minute": 30}, headers=trader_headers
    )
    assert res.json()["rate_limit_per_minute"] == 30
    res = await client.patch(
        f"{KEYS}/{created['id']}", json={"rate_limit_per_minute": None}, headers=trader_headers
    )
    assert res.json()["rate_limit_per_minute"] is None
    for bad in ({"rate_limit_per_minute": 61}, {"scopes": []}, {"scopes": None}, {"name": None}):
        res = await client.patch(f"{KEYS}/{created['id']}", json=bad, headers=trader_headers)
        assert res.status_code == 422, bad


async def test_patch_revoked_key_is_409(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers)
    await client.delete(f"{KEYS}/{created['id']}", headers=trader_headers)
    res = await client.patch(f"{KEYS}/{created['id']}", json={"name": "x"}, headers=trader_headers)
    assert res.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "scopes": ["market:write"]},
        {"name": "x", "scopes": ["admin"]},
        {"name": "x", "scopes": []},
        {"name": "", "scopes": ["stream"]},
        {"name": "x", "scopes": ["stream"], "rate_limit_per_minute": 61},  # trader tier is 60
        {"name": "x", "scopes": ["stream"], "rate_limit_per_minute": 0},
        {"name": "x", "scopes": ["stream"], "expires_in_days": 0},
    ],
)
async def test_create_validation_422(client: AsyncClient, trader_headers, body: dict) -> None:
    assert (await client.post(KEYS, json=body, headers=trader_headers)).status_code == 422


async def test_rate_limit_up_to_the_tier_is_accepted(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers, rate_limit_per_minute=60)
    assert created["rate_limit_per_minute"] == 60


async def test_other_users_keys_are_404(client: AsyncClient, trader_headers, other_headers):
    created = await create_key(client, trader_headers)
    path = f"{KEYS}/{created['id']}"
    assert (await client.delete(path, headers=other_headers)).status_code == 404
    assert (await client.patch(path, json={"name": "x"}, headers=other_headers)).status_code == 404
    assert (await client.get(f"{path}/usage", headers=other_headers)).status_code == 404
    assert (await client.get(KEYS, headers=other_headers)).json() == []
    assert (
        await client.get(f"{KEYS}/{uuid.uuid4()}/usage", headers=trader_headers)
    ).status_code == 404
    # still usable: the other user's DELETE did nothing
    assert (await client.get(INSTRUMENTS, headers=xkey(created["key"]))).status_code == 200


# --- scopes -----------------------------------------------------------------------------------


@pytest.fixture
async def instrument_id(session: AsyncSession) -> str:
    return str((await make_instrument(session)).id)


def _scoped_requests(iid: str) -> list[tuple[str, str, dict | None, str]]:
    """Every endpoint an API key can reach, with the scope it needs."""
    return [
        ("GET", INSTRUMENTS, None, "market:read"),
        ("GET", f"{INSTRUMENTS}/{iid}", None, "market:read"),
        ("GET", f"{INSTRUMENTS}/{iid}/candles?timeframe=1m", None, "market:read"),
        ("GET", "/api/v1/indicators", None, "indicators:read"),
        (
            "POST",
            f"{INSTRUMENTS}/{iid}/indicators",
            {"timeframe": "1m", "indicators": [{"name": "sma"}]},
            "indicators:read",
        ),
        ("GET", "/api/v1/strategies", None, "strategies:read"),
        (
            "POST",
            "/api/v1/strategies/rsi_reversal/preview",
            {"instrument_id": iid, "timeframe": "1m"},
            "strategies:read",
        ),
        ("GET", "/api/v1/signals", None, "signals:read"),
        ("GET", "/api/v1/signals?mine=true", None, "signals:read"),
    ]


async def test_scope_enforcement_on_every_endpoint_group(
    client: AsyncClient, trader_headers, instrument_id: str
) -> None:
    for method, path, body, scope in _scoped_requests(instrument_id):
        with_scope = await create_key(client, trader_headers, [scope], name="with")
        without = await create_key(client, trader_headers, [s for s in ALL if s != scope])

        res = await client.request(method, path, json=body, headers=xkey(with_scope["key"]))
        assert res.status_code == 200, (path, res.text)
        res = await client.request(method, path, json=body, headers=xkey(without["key"]))
        assert res.status_code == 403, path
        assert res.json()["detail"] == f"This API key lacks the '{scope}' scope"
        # JWT users are unaffected
        res = await client.request(method, path, json=body, headers=trader_headers)
        assert res.status_code == 200, path

        for created in (with_scope, without):
            await client.delete(f"{KEYS}/{created['id']}", headers=trader_headers)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/v1/users/me", None),
        ("PATCH", "/api/v1/users/me", {"full_name": "x"}),
        ("POST", "/api/v1/users/me/password", {"current_password": "a", "new_password": "b"}),
        ("GET", "/api/v1/me/strategies", None),
        ("GET", "/api/v1/me/api-keys", None),
        ("POST", "/api/v1/me/api-keys", {"name": "x", "scopes": ["stream"]}),
        ("GET", "/api/v1/admin/users", None),
        ("GET", "/api/v1/admin/api-keys", None),
        ("GET", "/api/v1/admin/rate-limits/stats", None),
        ("GET", "/api/v1/admin/realtime/stats", None),
        ("POST", "/api/v1/auth/logout", {"refresh_token": "x"}),
        ("POST", "/api/v1/auth/login", {"email": "admin@example.com", "password": "Passw0rd123"}),
        ("POST", "/api/v1/auth/refresh", {"refresh_token": "x"}),
        ("POST", "/api/v1/auth/register", {"email": "new@example.com", "password": "abcdefg1"}),
    ],
)
async def test_api_keys_never_reach_account_admin_or_auth(
    client: AsyncClient, admin_headers, method: str, path: str, body: dict | None
) -> None:
    created = await create_key(client, admin_headers, ALL)  # every scope, admin owner
    res = await client.request(method, path, json=body, headers=xkey(created["key"]))
    assert res.status_code in (401, 403), (path, res.status_code)
    assert res.json()["detail"] == "API keys cannot be used for this endpoint"


async def test_jwt_still_reaches_account_and_admin(client: AsyncClient, admin_headers) -> None:
    for path in ("/api/v1/users/me", "/api/v1/me/strategies", KEYS, "/api/v1/admin/api-keys"):
        assert (await client.get(path, headers=admin_headers)).status_code == 200, path


async def test_bearer_wins_over_api_key(client: AsyncClient, trader_headers) -> None:
    created = await create_key(client, trader_headers, ["stream"])  # no market:read
    headers = {**trader_headers, **xkey(created["key"])}
    assert (await client.get(INSTRUMENTS, headers=headers)).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200


async def test_no_credentials_still_401(client: AsyncClient) -> None:
    res = await client.get(INSTRUMENTS)
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"
    assert res.headers["www-authenticate"] == "Bearer"


# --- last_used_at -----------------------------------------------------------------------------


async def test_last_used_at_is_written_at_most_once_per_interval(
    client: AsyncClient, session: AsyncSession, redis_client: Redis, trader_headers
) -> None:
    created = await create_key(client, trader_headers)
    assert created["last_used_at"] is None
    key = created["key"]

    await client.get(INSTRUMENTS, headers=xkey(key))
    first = (await _row(session, created["id"])).last_used_at
    assert first is not None
    throttle = f"test-rl:used:{created['id']}"
    assert 0 < await redis_client.ttl(throttle) <= 60

    for _ in range(3):
        await client.get(INSTRUMENTS, headers=xkey(key))
    assert (await _row(session, created["id"])).last_used_at == first  # no DB write

    await redis_client.delete(throttle)  # the interval has passed
    await client.get(INSTRUMENTS, headers=xkey(key))
    assert (await _row(session, created["id"])).last_used_at > first


async def test_last_used_at_without_redis_uses_the_stored_value(session: AsyncSession, make_user):
    user = await make_user("t@example.com")
    row = ApiKey(user_id=user.id, name="k", prefix="abcdefgh", key_hash="0" * 64, scopes=["stream"])
    session.add(row)
    await session.commit()
    down = unreachable_redis()
    try:
        now = datetime.now(UTC)
        assert await api_key_service.touch(session, down, row, now) is True
        assert await api_key_service.touch(session, down, row, now + timedelta(seconds=30)) is False
        assert await api_key_service.touch(session, down, row, now + timedelta(seconds=61)) is True
    finally:
        await down.aclose()


# --- admin --------------------------------------------------------------------------------


async def test_admin_lists_filters_and_revokes(
    client: AsyncClient, admin_headers, trader_headers, other_headers, session: AsyncSession
) -> None:
    mine = await create_key(client, trader_headers, name="trader key")
    theirs = await create_key(client, other_headers, name="other key")
    await client.delete(f"{KEYS}/{theirs['id']}", headers=other_headers)

    res = await client.get("/api/v1/admin/api-keys", headers=admin_headers)
    assert res.status_code == 200
    page = res.json()
    assert page["total"] == 2
    by_id = {k["id"]: k for k in page["items"]}
    assert by_id[mine["id"]]["owner_email"] == "trader@example.com"
    assert by_id[theirs["id"]]["owner_email"] == "other@example.com"
    assert all("key" not in k and "key_hash" not in k for k in page["items"])

    res = await client.get("/api/v1/admin/api-keys?revoked=true", headers=admin_headers)
    assert [k["id"] for k in res.json()["items"]] == [theirs["id"]]
    res = await client.get("/api/v1/admin/api-keys?revoked=false", headers=admin_headers)
    assert [k["id"] for k in res.json()["items"]] == [mine["id"]]
    trader = await session.scalar(select(User).where(User.email == "trader@example.com"))
    res = await client.get(f"/api/v1/admin/api-keys?user_id={trader.id}", headers=admin_headers)
    assert [k["id"] for k in res.json()["items"]] == [mine["id"]]

    path = f"/api/v1/admin/api-keys/{mine['id']}"
    assert (await client.delete(path, headers=trader_headers)).status_code == 403
    assert (await client.delete(path, headers=admin_headers)).status_code == 204
    assert (await client.get(INSTRUMENTS, headers=xkey(mine["key"]))).status_code == 401
    missing = f"/api/v1/admin/api-keys/{uuid.uuid4()}"
    assert (await client.delete(missing, headers=admin_headers)).status_code == 404


async def test_admin_endpoints_need_admin(client: AsyncClient, trader_headers) -> None:
    for path in ("/api/v1/admin/api-keys", "/api/v1/admin/rate-limits/stats"):
        assert (await client.get(path, headers=trader_headers)).status_code == 403


# --- usage ----------------------------------------------------------------------------------


async def test_usage_counts_requests_and_rejections_per_day(
    client: AsyncClient, trader_headers, rate_limits
) -> None:
    created = await create_key(client, trader_headers, rate_limit_per_minute=3)
    for _ in range(4):
        await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    res = await client.get(f"{KEYS}/{created['id']}/usage", headers=trader_headers)
    assert res.status_code == 200
    days = res.json()
    assert len(days) == 7
    today = datetime.now(UTC).date()
    assert [d["date"] for d in days] == [
        (today - timedelta(days=n)).isoformat() for n in range(6, -1, -1)
    ]
    assert days[-1] == {"date": today.isoformat(), "requests": 3, "rejected": 1}
    assert all(d["requests"] == d["rejected"] == 0 for d in days[:-1])


async def test_usage_hash_expires_after_8_days(
    client: AsyncClient, trader_headers, rate_limits, redis_client: Redis
) -> None:
    created = await create_key(client, trader_headers)
    await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    usage = f"test-rl:usage:{created['id']}:{datetime.now(UTC).date().isoformat()}"
    assert await redis_client.hget(usage, "requests") == "1"
    assert 7 * 86400 < await redis_client.ttl(usage) <= 8 * 86400


# --- housekeeping ---------------------------------------------------------------------------


async def test_cleanup_deletes_old_refresh_tokens_and_revoked_keys(
    session: AsyncSession, make_user
) -> None:
    user = await make_user("t@example.com")
    now = datetime.now(UTC)
    day = timedelta(days=1)

    def token(expires_at, revoked_at=None) -> RefreshToken:
        return RefreshToken(
            id=uuid.uuid4(), user_id=user.id, expires_at=expires_at, revoked_at=revoked_at
        )

    tokens = {
        "expired_8d": token(now - 8 * day),
        "expired_6d": token(now - 6 * day),
        "revoked_8d": token(now + 6 * day, now - 8 * day),
        "revoked_6d": token(now + 6 * day, now - 6 * day),
        "active": token(now + day),
    }

    def key(prefix: str, revoked_at=None) -> ApiKey:
        return ApiKey(
            user_id=user.id,
            name=prefix,
            prefix=prefix,
            key_hash="0" * 64,
            scopes=["stream"],
            revoked_at=revoked_at,
        )

    keys = {
        "revoked_91d": key("aaaaaaaa", now - 91 * day),
        "revoked_89d": key("bbbbbbbb", now - 89 * day),
        "active": key("cccccccc"),
    }
    session.add_all([*tokens.values(), *keys.values()])
    await session.commit()
    token_ids = {name: row.id for name, row in tokens.items()}

    result = await housekeeping.cleanup(session, now)
    assert result.refresh_tokens >= 2 and result.api_keys >= 1

    session.expire_all()
    left_tokens = set(await session.scalars(select(RefreshToken.id)))
    assert left_tokens >= {token_ids[k] for k in ("expired_6d", "revoked_6d", "active")}
    assert not left_tokens & {token_ids[k] for k in ("expired_8d", "revoked_8d")}
    left_keys = set(await session.scalars(select(ApiKey.prefix)))
    assert left_keys == {"bbbbbbbb", "cccccccc"}


def test_cleanup_is_scheduled_daily_at_3_utc() -> None:
    entry = celery_app.conf.beat_schedule["housekeeping-cleanup"]
    assert entry["task"] == "housekeeping.cleanup"
    schedule = entry["schedule"]
    assert schedule.hour == {3} and schedule.minute == {0}
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.tasks["housekeeping.cleanup"].name == housekeeping_tasks.cleanup.name
