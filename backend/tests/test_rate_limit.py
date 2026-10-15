"""Rate limiting: tiers, costs, buckets, headers, recovery, per-key limits, auth endpoint
limits and the failed-login lockout, client IPs behind the proxy, and Redis being down.

The ``rate_limits`` fixture turns limiting on with a frozen limiter clock, so allowances are
exact and "a minute later" is ``frozen_clock.advance(60)`` instead of a sleep.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core import rate_limit
from app.core.redis import set_redis
from app.core.security import create_access_token
from app.main import app
from app.models.user import UserRole
from tests.api_key_utils import create_key, unreachable_redis, xkey
from tests.utils import DEFAULT_PASSWORD, bearer

ME = "/api/v1/users/me"
LOGIN = "/api/v1/auth/login"
TOKEN = "/api/v1/auth/token"
INSTRUMENTS = "/api/v1/market/instruments"
PREVIEW = "/api/v1/strategies/rsi_reversal/preview"
TIERS = {UserRole.trader: 60, UserRole.analyst: 300, UserRole.expert: 300, UserRole.admin: 1000}


@pytest.fixture
def make_headers(make_user):
    """JWT headers without going through /auth/login (which is rate limited itself)."""

    async def _make(email: str, role: UserRole = UserRole.trader) -> dict[str, str]:
        return bearer(create_access_token(await make_user(email, role=role)))

    return _make


@asynccontextmanager
async def client_from(ip: str, *, trusted_proxy: str | None = None) -> AsyncIterator[AsyncClient]:
    """A client connecting from ``ip``; with ``trusted_proxy`` the app is wrapped like uvicorn
    runs it (--proxy-headers --forwarded-allow-ips=<trusted_proxy>). Needs the ``client``
    fixture (DB overrides)."""
    asgi = ProxyHeadersMiddleware(app, trusted_hosts=trusted_proxy) if trusted_proxy else app
    transport = ASGITransport(app=asgi, client=(ip, 40000))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def spend(client: AsyncClient, headers: dict, path: str = ME, *, limit: int) -> Response:
    """Send requests until the first 429 (at most ``limit + 1``); return that 429."""
    for i in range(limit + 1):
        res = await client.get(path, headers=headers)
        if res.status_code == 429:
            assert i == limit, f"429 after {i} requests, expected {limit}"
            return res
        assert res.status_code == 200, res.text
    raise AssertionError(f"no 429 after {limit + 1} requests")


def assert_429(res: Response, retry_after: int | None = None) -> None:
    assert res.status_code == 429
    body = res.json()
    assert body["detail"] == "Rate limit exceeded"
    assert body["retry_after"] == int(res.headers["retry-after"]) >= 1
    if retry_after is not None:
        assert body["retry_after"] == retry_after


# --- per identity -----------------------------------------------------------------------------


@pytest.mark.parametrize("role", list(UserRole))
async def test_exact_allowance_per_tier(
    client: AsyncClient, rate_limits, make_headers, role: UserRole
) -> None:
    assert rate_limits.tier_limit(role.value) == TIERS[role]
    headers = await make_headers(f"{role.value}@example.com", role)
    res = await spend(client, headers, limit=TIERS[role])
    assert_429(res, retry_after=1)  # one request is allowed again after 60 s / limit (< 1 s)
    assert res.headers["ratelimit-limit"] == str(TIERS[role])
    assert res.headers["ratelimit-remaining"] == "0"
    assert res.headers["ratelimit-reset"] == "60"


async def test_headers_on_every_limited_response(
    client: AsyncClient, rate_limits, make_headers
) -> None:
    headers = await make_headers("t@example.com")
    first = await client.get(ME, headers=headers)
    assert (first.headers["ratelimit-limit"], first.headers["ratelimit-remaining"]) == ("60", "59")
    assert first.headers["ratelimit-reset"] == "1"
    assert "retry-after" not in first.headers
    second = await client.get(ME, headers=headers)
    assert (second.headers["ratelimit-remaining"], second.headers["ratelimit-reset"]) == ("58", "2")

    # error responses and raw Response bodies carry them too
    missing = await client.get(f"{INSTRUMENTS}/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404 and missing.headers["ratelimit-remaining"] == "57"
    catalog = await client.get("/api/v1/strategies", headers=headers)
    assert catalog.status_code == 200 and catalog.headers["ratelimit-remaining"] == "56"


async def test_health_and_unauthenticated_requests_are_not_identity_limited(
    client: AsyncClient, rate_limits
) -> None:
    for path in ("/api/v1/health", "/api/v1/health/ready"):
        assert "ratelimit-limit" not in (await client.get(path)).headers
    res = await client.get(INSTRUMENTS)
    assert res.status_code == 401 and "ratelimit-limit" not in res.headers


async def test_expensive_endpoints_cost_5(client: AsyncClient, rate_limits, make_headers) -> None:
    assert rate_limits.rate_limit_expensive_cost == 5
    headers = await make_headers("t@example.com")
    body = {"instrument_id": str(uuid.uuid4()), "timeframe": "1m"}
    for i in range(12):  # 12 x 5 = 60
        res = await client.post(PREVIEW, json=body, headers=headers)
        assert res.status_code == 404, res.text  # unknown instrument, still charged
        assert res.headers["ratelimit-remaining"] == str(60 - 5 * (i + 1))
    assert_429(await client.post(PREVIEW, json=body, headers=headers), retry_after=5)
    assert_429(await client.get(ME, headers=headers))  # same bucket

    other = await make_headers("u@example.com")
    res = await client.post(
        f"{INSTRUMENTS}/{uuid.uuid4()}/indicators",
        json={"timeframe": "1m", "indicators": [{"name": "sma"}]},
        headers=other,
    )
    assert res.status_code == 404 and res.headers["ratelimit-remaining"] == "55"
    res = await client.get("/api/v1/indicators", headers=other)
    assert res.headers["ratelimit-remaining"] == "54"  # the catalog costs 1


async def test_independent_buckets_per_identity(
    client: AsyncClient, rate_limits, make_headers
) -> None:
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    created = await create_key(client, a)  # one request of a's bucket
    await spend(client, a, limit=59)
    assert (await client.get(ME, headers=b)).status_code == 200
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"]))  # the key's own bucket
    assert res.status_code == 200 and res.headers["ratelimit-remaining"] == "59"
    assert (await client.get(ME, headers=a)).status_code == 429


async def test_recovery_after_the_window(
    client: AsyncClient, rate_limits, frozen_clock, make_headers
) -> None:
    headers = await make_headers("t@example.com")
    await spend(client, headers, limit=60)
    frozen_clock.advance(1)  # one request per second comes back
    assert (await client.get(ME, headers=headers)).status_code == 200
    assert (await client.get(ME, headers=headers)).status_code == 429
    frozen_clock.advance(60)  # the whole minute
    await spend(client, headers, limit=60)


async def test_custom_per_key_limit(client: AsyncClient, rate_limits, make_headers) -> None:
    headers = await make_headers("t@example.com")
    created = await create_key(client, headers, rate_limit_per_minute=3)
    res = await spend(client, xkey(created["key"]), INSTRUMENTS, limit=3)
    assert res.headers["ratelimit-limit"] == "3"
    assert_429(res, retry_after=20)  # 60 s / 3
    plain = await create_key(client, headers, name="plain")  # no own limit: the owner's tier
    res = await client.get(INSTRUMENTS, headers=xkey(plain["key"]))
    assert res.headers["ratelimit-limit"] == "60"
    assert (await client.get(ME, headers=headers)).status_code == 200  # the user's own bucket


async def test_key_limit_never_exceeds_the_owners_current_tier(
    client: AsyncClient, session: AsyncSession, rate_limits, make_user
) -> None:
    user = await make_user("a@example.com", role=UserRole.analyst)
    created = await create_key(client, bearer(create_access_token(user)), rate_limit_per_minute=200)
    user.role = UserRole.trader  # demoted: tier 60 < 200
    await session.commit()
    res = await client.get(INSTRUMENTS, headers=xkey(created["key"]))
    assert res.headers["ratelimit-limit"] == "60"


async def test_cost_above_a_tiny_key_limit_is_capped(
    client: AsyncClient, rate_limits, make_headers
) -> None:
    created = await create_key(
        client, await make_headers("t@example.com"), ["strategies:read"], rate_limit_per_minute=2
    )
    body = {"instrument_id": str(uuid.uuid4()), "timeframe": "1m"}
    res = await client.post(PREVIEW, json=body, headers=xkey(created["key"]))
    assert res.status_code == 404 and res.headers["ratelimit-remaining"] == "0"


async def test_admin_stats_count_429s_by_tier_and_group(
    client: AsyncClient, rate_limits, make_headers
) -> None:
    trader = await make_headers("t@example.com")
    admin = await make_headers("admin@example.com", UserRole.admin)
    await spend(client, trader, limit=60)
    await client.get(ME, headers=trader)  # a second 429
    res = await client.get("/api/v1/admin/rate-limits/stats", headers=admin)
    assert res.status_code == 200
    stats = res.json()
    assert stats["window_minutes"] == 60
    assert stats["rejected"]["total"] == 2
    assert stats["rejected"]["by_tier"] == {"trader": 2}
    assert stats["rejected"]["by_group"] == {"users": 2}
    assert stats["rejected"]["by_tier_and_group"] == [
        {"tier": "trader", "group": "users", "count": 2}
    ]
    assert set(stats["fail_open"]) == {"process_total", "process_last_hour"}


# --- auth endpoints -------------------------------------------------------------------------


async def _login(c: AsyncClient, email: str, password: str = "Wrong12345") -> Response:
    return await c.post(LOGIN, json={"email": email, "password": password})


async def test_login_per_ip(client: AsyncClient, rate_limits) -> None:
    for i in range(10):
        assert (await _login(client, f"u{i}@example.com")).status_code == 401
    res = await _login(client, "u10@example.com")
    assert_429(res, retry_after=6)
    assert res.headers["ratelimit-limit"] == "10"
    # /auth/token shares the login bucket
    form = {"username": "x@example.com", "password": "Wrong12345"}
    assert (await client.post(TOKEN, data=form)).status_code == 429
    async with client_from("198.51.100.7") as other_ip:
        assert (await _login(other_ip, "u11@example.com")).status_code == 401


async def test_login_per_email(client: AsyncClient, rate_limits) -> None:
    for i in range(5):
        async with client_from(f"198.51.100.{i + 1}") as c:
            assert (await _login(c, "victim@example.com")).status_code == 401
    async with client_from("198.51.100.99") as c:
        res = await _login(c, "victim@example.com")
        assert_429(res, retry_after=12)
        assert res.headers["ratelimit-limit"] == "5"
        assert (await _login(c, "someone-else@example.com")).status_code == 401


async def test_token_endpoint_per_email(client: AsyncClient, rate_limits) -> None:
    form = {"username": "victim@example.com", "password": "Wrong12345"}
    for i in range(5):
        async with client_from(f"198.51.100.{i + 1}") as c:
            assert (await c.post(TOKEN, data=form)).status_code == 401
    assert (await client.post(TOKEN, data=form)).status_code == 429


async def _fail(email: str, times: int, frozen_clock, first_ip: int = 1) -> None:
    """``times`` failed logins, 5 per limiter minute, each from its own IP."""
    for i in range(times):
        if i and i % 5 == 0:
            frozen_clock.advance(61)
        async with client_from(f"203.0.113.{first_ip + i}") as c:
            res = await _login(c, email)
            assert res.status_code == 401, (i, res.text)


async def test_lockout_after_10_failures_refuses_the_right_password(
    client: AsyncClient, rate_limits, frozen_clock, make_user, redis_client: Redis
) -> None:
    await make_user("victim@example.com")
    await _fail("victim@example.com", 10, frozen_clock)
    frozen_clock.advance(61)  # the per-email limit is not what refuses it
    res = await _login(client, "victim@example.com", DEFAULT_PASSWORD)
    assert_429(res)
    assert 890 <= int(res.headers["retry-after"]) <= 900
    frozen_clock.advance(600)
    assert (await _login(client, "victim@example.com", DEFAULT_PASSWORD)).status_code == 429

    # 15 minutes later (the lock is a real Redis TTL): logging in works again
    lock = [k async for k in redis_client.scan_iter(match="test-rl:login-lock:*")]
    assert len(lock) == 1 and 890 <= await redis_client.ttl(lock[0]) <= 900
    await redis_client.delete(*lock)
    assert (await _login(client, "victim@example.com", DEFAULT_PASSWORD)).status_code == 200


async def test_9_failures_do_not_lock(client: AsyncClient, rate_limits, frozen_clock, make_user):
    await make_user("victim@example.com")
    await _fail("victim@example.com", 9, frozen_clock)
    frozen_clock.advance(61)
    assert (await _login(client, "victim@example.com", DEFAULT_PASSWORD)).status_code == 200


async def test_success_clears_the_failure_counter(
    client: AsyncClient, rate_limits, frozen_clock, make_user
) -> None:
    await make_user("victim@example.com")
    await _fail("victim@example.com", 9, frozen_clock)
    frozen_clock.advance(61)
    assert (await _login(client, "victim@example.com", DEFAULT_PASSWORD)).status_code == 200
    frozen_clock.advance(61)
    await _fail("victim@example.com", 9, frozen_clock, first_ip=50)  # 9 more: 18 in total
    frozen_clock.advance(61)
    assert (await _login(client, "victim@example.com", DEFAULT_PASSWORD)).status_code == 200


async def test_unknown_emails_get_the_same_answers(
    client: AsyncClient, rate_limits, frozen_clock, make_user
) -> None:
    await make_user("known@example.com")
    async with client_from("192.0.2.1") as c:
        known, unknown = await _login(c, "known@example.com"), await _login(c, "nobody@example.com")
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    frozen_clock.advance(61)
    # the lockout applies to unknown emails exactly like to known ones: 1 + 8 + 1 failures
    await _fail("known@example.com", 8, frozen_clock, first_ip=100)
    await _fail("nobody@example.com", 8, frozen_clock, first_ip=150)
    frozen_clock.advance(61)
    known = await _login(client, "known@example.com")
    unknown = await _login(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 401  # the 10th failure locks
    known, unknown = (
        await _login(client, "known@example.com"),
        await _login(client, "nobody@example.com"),
    )
    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()


async def test_register_and_refresh_per_ip(client: AsyncClient, rate_limits) -> None:
    for i in range(5):
        body = {"email": f"new{i}@example.com", "password": "abcdefg1"}
        assert (await client.post("/api/v1/auth/register", json=body)).status_code == 201
    body = {"email": "new5@example.com", "password": "abcdefg1"}
    assert_429(await client.post("/api/v1/auth/register", json=body))
    for _ in range(30):
        res = await client.post("/api/v1/auth/refresh", json={"refresh_token": "x"})
        assert res.status_code == 401
    assert_429(await client.post("/api/v1/auth/refresh", json={"refresh_token": "x"}))


# --- client IP ------------------------------------------------------------------------------


async def test_spoofed_forwarded_for_from_a_direct_client_is_ignored(
    client: AsyncClient, rate_limits
) -> None:
    async with client_from("203.0.113.9", trusted_proxy="10.0.0.2") as direct:
        for i in range(10):
            spoof = {"X-Forwarded-For": f"192.0.2.{i}"}
            res = await direct.post(
                LOGIN, json={"email": f"u{i}@example.com", "password": "x1"}, headers=spoof
            )
            assert res.status_code == 401
        res = await direct.post(
            LOGIN,
            json={"email": "u10@example.com", "password": "x1"},
            headers={"X-Forwarded-For": "192.0.2.200"},
        )
        assert res.status_code == 429  # all counted for 203.0.113.9


async def test_forwarded_for_from_the_proxy_is_honoured(client: AsyncClient, rate_limits) -> None:
    async with client_from("10.0.0.2", trusted_proxy="10.0.0.2") as proxy:
        for i in range(12):  # 12 different clients behind the proxy: none is over 10/min
            res = await proxy.post(
                LOGIN,
                json={"email": f"u{i}@example.com", "password": "x1"},
                headers={"X-Forwarded-For": f"192.0.2.{i}"},
            )
            assert res.status_code == 401
        for _ in range(10):  # the same client 10 more times: limited on its own IP
            await proxy.post(
                LOGIN,
                json={"email": "z@example.com", "password": "x1"},
                headers={"X-Forwarded-For": "192.0.2.0"},
            )
        res = await proxy.post(
            LOGIN,
            json={"email": "y@example.com", "password": "x1"},
            headers={"X-Forwarded-For": "192.0.2.0"},
        )
        assert res.status_code == 429


# --- Redis down -----------------------------------------------------------------------------


@pytest.fixture
async def redis_down() -> AsyncIterator[None]:
    down = unreachable_redis()
    set_redis(down)
    yield
    await down.aclose()


async def test_redis_down_fails_open_except_login(
    client: AsyncClient, rate_limits, make_headers, make_user, redis_down
) -> None:
    headers = await make_headers("t@example.com")
    before = rate_limit.fail_open.total
    res = await client.get(ME, headers=headers)
    assert res.status_code == 200 and "ratelimit-limit" not in res.headers
    assert rate_limit.fail_open.total == before + 1

    res = await _login(client, "t@example.com", DEFAULT_PASSWORD)
    assert res.status_code == 503
    assert res.json()["detail"] == "Login is temporarily unavailable"
    form = {"username": "t@example.com", "password": DEFAULT_PASSWORD}
    assert (await client.post(TOKEN, data=form)).status_code == 503

    body = {"email": "new@example.com", "password": "abcdefg1"}
    assert (await client.post("/api/v1/auth/register", json=body)).status_code == 201
    assert rate_limit.fail_open.total == before + 2
    assert rate_limit.fail_open.last_hour() >= 2
