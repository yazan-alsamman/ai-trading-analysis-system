"""Y14: /api/v1/analysis/chart-image. Validation (magic bytes, size, dimensions), auth, the
daily quota per role and its reset, the duplicate cache, the stored rows (never the image),
history pagination, own rows only, the feature flag, the rate-limit cost and the admin status.
Gemini is never called: the client is a fake."""

import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.chart_analysis import ChartAnalysisRecord
from app.models.user import UserRole
from app.notifications import preferences as prefs_mod
from app.vision import gemini, service
from app.vision.schemas import DISCLAIMERS
from tests.test_chart_vision import FAKE_KEY, FakeClient, answer, png, response
from tests.utils import bearer

URL = "/api/v1/analysis/chart-image"


@pytest.fixture
async def fake(monkeypatch: pytest.MonkeyPatch, redis_client):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "chart_analysis_enabled", True)
    monkeypatch.setattr(gemini, "BACKOFF_SECONDS", (0.0, 0.0))
    client = FakeClient(response(answer()))
    monkeypatch.setattr(gemini, "get_client", lambda: client)
    async for key in redis_client.scan_iter(f"{service.QUOTA_PREFIX}*"):
        await redis_client.delete(key)
    yield client
    async for key in redis_client.scan_iter(f"{service.QUOTA_PREFIX}*"):
        await redis_client.delete(key)


@pytest.fixture
async def people(make_user):
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    return (alice, bearer(create_access_token(alice))), (bob, bearer(create_access_token(bob)))


async def post(client: AsyncClient, headers, data: bytes | None = None, **form):
    files = {"image": ("chart.png", data if data is not None else png(), "image/png")}
    return await client.post(URL, files=files, data=form, headers=headers)


def colors(n: int) -> list[bytes]:
    return [png(color=(10 * i, 100, 200)) for i in range(n)]


async def test_analyse_and_store_without_the_image(
    client: AsyncClient, session: AsyncSession, people, fake
) -> None:
    (alice, ah), _ = people
    data = png()
    res = await post(client, ah, data, language="en", symbol="XAU/USD", timeframe="15m")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["status"], body["language"], body["cached"]) == ("ok", "en", False)
    assert (body["symbol_hint"], body["timeframe_hint"]) == ("XAU/USD", "15m")
    assert (body["model"], body["prompt_version"]) == ("gemini-3.6-flash", "chart_v1")
    result = body["result"]
    assert result["trend"] == "up" and result["idea"]["risk_reward"] == 2.0
    assert result["disclaimer"] == DISCLAIMERS["en"] and body["error"] is None
    assert body["usage"]["input_tokens"] == 1290 and body["usage"]["output_tokens"] == 310
    assert body["image"]["mime"] == "image/png" and body["image"]["width"] == 800
    row = await session.get(ChartAnalysisRecord, body["id"])
    assert row.user_id == alice.id and row.status == "ok" and len(row.image_sha256) == 64
    columns = {c.name for c in ChartAnalysisRecord.__table__.columns}
    assert not {"image", "data", "image_data"} & columns  # only the hash is kept
    assert len(fake.calls) == 1


async def test_validation_and_auth(client: AsyncClient, people, fake, monkeypatch) -> None:
    (_, ah), _ = people
    assert (await post(client, {})).status_code == 401
    # the type comes from the bytes, not the header or the file name
    res = await client.post(
        URL, files={"image": ("x.jpg", png(), "text/plain")}, data={"language": "ar"}, headers=ah
    )
    assert res.status_code == 200 and res.json()["image"]["mime"] == "image/png"
    gif = await client.post(URL, files={"image": ("x.png", b"GIF89a" + b"\0" * 500,
                                                  "image/png")}, headers=ah)  # fmt: skip
    assert gif.status_code == 415 and gif.json()["detail"]["code"] == "unsupported_image"
    small = await post(client, ah, png(199, 400))
    assert small.status_code == 422 and small.json()["detail"]["code"] == "image_too_small"
    monkeypatch.setattr(get_settings(), "chart_image_max_bytes", 2000)
    big = await post(client, ah, png(900, 900, color=(1, 2, 3)) + b"\0" * 3000)
    assert big.status_code == 413 and big.json()["detail"]["code"] == "image_too_large"
    assert (await post(client, ah, language="fr")).status_code == 422
    assert (await post(client, ah, timeframe="fifteen minutes")).status_code == 422
    assert (await post(client, ah, symbol="x" * 40)).status_code == 422
    assert (await client.post(URL, headers=ah)).status_code == 422  # no image
    assert len(fake.calls) == 1  # only the valid upload reached the model


async def test_language_defaults_to_the_profile(
    client: AsyncClient, session: AsyncSession, people, fake
) -> None:
    (alice, ah), (bob, bh) = people
    row = await prefs_mod.get_or_create(session, bob.id)
    row.language = "en"
    await session.commit()
    assert (await post(client, ah)).json()["language"] == "ar"  # no profile: ar
    res = (await post(client, bh)).json()
    assert res["language"] == "en" and res["result"]["disclaimer"] == DISCLAIMERS["en"]
    assert "Requested language: en" in fake.calls[-1]["contents"][1].text


async def test_duplicates_are_free(client: AsyncClient, people, fake) -> None:
    (_, ah), (_, bh) = people
    data = png()
    first = (await post(client, ah, data, language="en", symbol="XAU/USD")).json()
    again = (await post(client, ah, data, language="en", symbol="XAU/USD")).json()
    assert again["cached"] is True and again["id"] == first["id"] and len(fake.calls) == 1
    quota = (await client.get(f"{URL}/quota", headers=ah)).json()
    assert quota["used"] == 1  # the duplicate was not counted
    await post(client, ah, data, language="ar", symbol="XAU/USD")  # another language: a call
    await post(client, ah, data, language="en")  # other hints: a call
    await post(client, bh, data, language="en", symbol="XAU/USD")  # another user: a call
    assert len(fake.calls) == 4


async def test_not_a_chart_is_422_and_counted(client: AsyncClient, people, fake) -> None:
    (_, ah), _ = people
    fake.answers = [response(answer(is_chart=False))]
    data = png(color=(250, 250, 250))
    res = await post(client, ah, data)
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "not_a_chart" and detail["analysis_id"]
    stored = (await client.get(f"{URL}/{detail['analysis_id']}", headers=ah)).json()
    assert stored["status"] == "not_chart" and stored["result"]["is_chart"] is False
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 1
    again = await post(client, ah, data)  # the duplicate: 422 again, no call, no quota
    assert again.status_code == 422 and len(fake.calls) == 1
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 1


async def test_refused_and_unavailable(
    client: AsyncClient, session: AsyncSession, people, fake
) -> None:
    (_, ah), _ = people
    fake.answers = [response(None)]  # an empty parsed answer
    refused = await post(client, ah, png(color=(1, 1, 1)))
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "empty_answer"
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 1  # the model ran

    from google.genai import errors  # noqa: PLC0415

    fake.answers = [errors.ServerError(503, {"error": {"code": 503, "message": "overloaded"}})]
    down = await post(client, ah, png(color=(2, 2, 2)))
    assert down.status_code == 503 and down.headers["Retry-After"] == "30"
    assert down.json()["detail"]["code"] == "model_unavailable"
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 1  # given back
    statuses = await session.scalars(
        select(ChartAnalysisRecord.status).order_by(ChartAnalysisRecord.created_at)
    )
    assert list(statuses) == ["refused", "error"]
    history = (await client.get(URL, headers=ah)).json()["items"]
    assert history[0]["error"]["code"] == "model_unavailable" and history[0]["result"] is None


@pytest.mark.parametrize(
    ("role", "limit"),
    [(UserRole.trader, 5), (UserRole.analyst, 20), (UserRole.expert, 20), (UserRole.admin, 100)],
)
async def test_quota_per_role(client: AsyncClient, make_user, fake, role, limit) -> None:
    user = await make_user(f"{role.value}@example.com", role=role)
    headers = bearer(create_access_token(user))
    quota = (await client.get(f"{URL}/quota", headers=headers)).json()
    assert (quota["limit"], quota["used"], quota["remaining"]) == (limit, 0, limit)


async def test_quota_is_enforced_and_resets(
    client: AsyncClient, people, fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    (_, ah), _ = people
    now = datetime(2026, 10, 27, 22, 0, tzinfo=UTC)
    monkeypatch.setattr(service, "utcnow", lambda: now)
    images = colors(7)
    for data in images[:5]:
        assert (await post(client, ah, data)).status_code == 200
    over = await post(client, ah, images[5])
    assert over.status_code == 429
    assert over.headers["Retry-After"] == str(2 * 3600)  # to 00:00 UTC
    assert over.json()["detail"]["code"] == "quota_exceeded"
    quota = (await client.get(f"{URL}/quota", headers=ah)).json()
    assert (quota["used"], quota["remaining"]) == (5, 0)
    assert quota["resets_at"] == "2026-10-28T00:00:00Z"
    assert len(fake.calls) == 5
    # a duplicate still works when the quota is used up
    assert (await post(client, ah, images[0])).json()["cached"] is True

    now = now + timedelta(hours=3)  # the next UTC day
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 0
    assert (await post(client, ah, images[6])).status_code == 200


async def test_history_get_and_delete(
    client: AsyncClient, session: AsyncSession, people, fake
) -> None:
    (_, ah), (_, bh) = people
    ids = [(await post(client, ah, data)).json()["id"] for data in colors(3)]
    page = (await client.get(URL, params={"limit": 2}, headers=ah)).json()
    assert page["total"] == 3 and [i["id"] for i in page["items"]] == ids[::-1][:2]
    rest = (await client.get(URL, params={"limit": 2, "offset": 2}, headers=ah)).json()
    assert [i["id"] for i in rest["items"]] == [ids[0]]
    assert (await client.get(URL, headers=bh)).json()["total"] == 0  # isolated
    assert (await client.get(f"{URL}/{ids[0]}", headers=ah)).status_code == 200
    assert (await client.get(f"{URL}/{ids[0]}", headers=bh)).status_code == 404
    assert (await client.delete(f"{URL}/{ids[0]}", headers=bh)).status_code == 404
    assert (await client.delete(f"{URL}/{ids[0]}", headers=ah)).status_code == 204
    assert (await client.get(f"{URL}/{ids[0]}", headers=ah)).status_code == 404
    assert (await client.get(URL, params={"limit": 101}, headers=ah)).status_code == 422
    count = await session.scalar(select(func.count()).select_from(ChartAnalysisRecord))
    assert count == 2


async def test_disabled_feature(
    client: AsyncClient, people, admin_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    (_, ah), _ = people
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "")
    for res in (
        await post(client, ah),
        await client.get(URL, headers=ah),
        await client.get(f"{URL}/quota", headers=ah),
    ):
        assert res.status_code == 503
        assert res.json()["detail"] == {
            "code": "not_configured",
            "message": "chart analysis is not configured",
            "reason": "GEMINI_API_KEY is not set",
        }
    status = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    assert status["chart_analysis"]["enabled"] is False  # a state, not an error
    assert status["chart_analysis"]["disabled_reason"] == "GEMINI_API_KEY is not set"
    assert "error" not in status["chart_analysis"] and status["database"]["migration"]
    monkeypatch.setattr(settings, "gemini_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "chart_analysis_enabled", False)
    assert (await post(client, ah)).json()["detail"]["reason"] == "CHART_ANALYSIS_ENABLED=false"
    monkeypatch.setattr(settings, "chart_analysis_enabled", True)
    status = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    assert status["chart_analysis"]["enabled"] is True
    assert status["chart_analysis"]["model"] == "gemini-3.6-flash"


async def test_expensive_rate_limit(client: AsyncClient, people, fake, rate_limits) -> None:
    (_, ah), _ = people
    res = await post(client, ah)
    assert res.status_code == 200
    cost = rate_limits.rate_limit_expensive_cost
    remaining = int(res.headers["RateLimit-Remaining"])
    assert remaining == rate_limits.rate_limit_trader - cost  # the expensive-endpoint cost


async def test_admin_status_counts(client: AsyncClient, people, fake, admin_headers) -> None:
    (_, ah), _ = people
    await post(client, ah)
    status = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    last = status["chart_analysis"]["last_24h"]["ok"]
    assert last["count"] == 1 and last["input_tokens"] == 1290 and last["output_tokens"] == 310


def test_png_helper_is_deterministic() -> None:
    assert io.BytesIO(png()).getvalue() == png()


async def test_busy_when_no_slot_is_free(
    client: AsyncClient, people, fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One analysis in flight per worker (CHART_ANALYSIS_MAX_CONCURRENT=1): a second one that
    cannot get a slot in time is 503 busy, and takes no quota."""
    (_, ah), _ = people
    assert get_settings().chart_analysis_max_concurrent == 1
    monkeypatch.setattr(service, "QUEUE_SECONDS", 0.2)
    fake.delay = 1.0
    first, second = colors(2)
    a, b = await asyncio.gather(post(client, ah, first), post(client, ah, second))
    assert sorted([a.status_code, b.status_code]) == [200, 503]
    busy = a if a.status_code == 503 else b
    assert busy.json()["detail"]["code"] == "busy" and busy.headers["Retry-After"] == "10"
    assert (await client.get(f"{URL}/quota", headers=ah)).json()["used"] == 1
    fake.delay = 0.0
    assert (await post(client, ah, first if busy is a else second)).status_code == 200
