"""B9 explanations (app/ai/explain.py, the ai.explain task, GET /ai/setups/{id}/explanation):
Fadi's rule (extra 5) on storing and on serving: verified text, else the template text, else
nothing ("unavailable"); a 404 from ai-service is unavailable, quietly."""

import logging
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import explain, store
from app.ai.client import AIUnavailableError
from app.core.security import create_access_token
from app.models.ai import AISetupExplanation
from app.models.instrument import MarketType
from app.notifications.templates import inbox
from app.tasks import ai as ai_tasks
from tests.market_utils import make_instrument
from tests.test_ai_evaluate import fake, fake_client
from tests.test_ai_store import request_at, response, setup
from tests.utils import bearer

SETUP_ID = "explain-me"
URL = f"/api/v1/ai/setups/{SETUP_ID}/explanation"


@pytest.fixture(autouse=True)
def _fake():
    fake.STATE.reset()


@pytest.fixture
async def armed(session: AsyncSession):
    gold = await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity)
    req = request_at(datetime(2026, 10, 19, 14, 15, tzinfo=UTC))
    await store.apply_evaluation(session, gold, req, response(req, new=[setup(SETUP_ID, "ARMED")]))


async def ask(session_factory, lang: str = "en") -> str:
    return await explain.explain(session_factory, SETUP_ID, lang, client=fake_client())


@pytest.mark.parametrize(
    ("mode", "outcome", "status", "stored"),
    [
        ("verified", "stored", "verified", True),
        ("template", "stored", "template", True),  # verified false, template: shown
        ("unverified", "unavailable", "unavailable", False),  # neither: never stored
        ("404", "unavailable", "unavailable", False),  # no /v1/explain yet (P7)
    ],
)
async def test_storing_follows_the_rule(
    session, session_factory, armed, mode, outcome, status, stored, caplog
) -> None:
    fake.STATE.modes["explain"] = mode
    caplog.set_level(logging.INFO, logger="app.ai.explain")
    assert await ask(session_factory) == outcome
    row = await session.get(AISetupExplanation, (SETUP_ID, "en"))
    assert (row is not None) == stored
    shown = await explain.stored(session, SETUP_ID, "en")
    assert shown.status == status
    assert (shown.text is None) == (status == "unavailable")
    if mode == "404":  # quietly: no warning
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert "no /v1/explain yet" in caplog.text


async def test_serving_hides_an_unverified_text_stored_earlier(
    session, client: AsyncClient, armed, make_user
) -> None:
    """B11 stored unverified answers; they are never served."""
    session.add(
        AISetupExplanation(
            setup_id=SETUP_ID, lang="en", text="EV 9.9R!", verified=False, template_used=False
        )
    )
    session.add(
        AISetupExplanation(
            setup_id=SETUP_ID, lang="ar", text="قالب", verified=False, template_used=True
        )
    )
    await session.commit()
    user = await make_user("reader@example.com")
    headers = bearer(create_access_token(user))
    res = await client.get(URL, params={"lang": "en"}, headers=headers)
    assert res.status_code == 200
    assert res.json() == {
        "setup_id": SETUP_ID,
        "lang": "en",
        "explanation": None,
        "explanation_status": "unavailable",
    }
    res = await client.get(URL, params={"lang": "ar"}, headers=headers)
    assert (res.json()["explanation"], res.json()["explanation_status"]) == ("قالب", "template")
    assert (await client.get(URL.replace(SETUP_ID, "nope"), headers=headers)).status_code == 404
    assert (await client.get(URL)).status_code == 401


async def test_existing_explanation_is_not_asked_again(session, session_factory, armed) -> None:
    fake.STATE.modes["explain"] = "verified"
    assert await ask(session_factory) == "stored"
    assert await ask(session_factory) == "exists"
    assert len([r for r in fake.STATE.requests if r["path"] == "/v1/explain"]) == 1


async def test_5xx_is_retried_a_bounded_number_of_times(
    session_factory, armed, monkeypatch
) -> None:
    fake.STATE.modes["explain"] = "503"
    with pytest.raises(AIUnavailableError):
        await ask(session_factory)
    calls = []

    def unavailable(_fn):
        calls.append(1)
        raise AIUnavailableError("down", attempts=3, last_error="503")

    monkeypatch.setattr(ai_tasks, "run_async", unavailable)
    assert ai_tasks.explain.apply(args=(SETUP_ID, "en")).get() == "unavailable"
    assert len(calls) == ai_tasks.EXPLAIN_RETRIES + 1


def test_alert_text_says_unavailable() -> None:
    data = {
        "state": "ARMED",
        "direction": "buy",
        "entry": 2400.0,
        "sl": 2395.0,
        "tp": 2410.0,
        "grade": None,
        "probability": 0.58,
        "r_multiple": 2.0,
        "instrument": {"symbol": "XAU/USD", "price_precision": 2},
        "explanation_status": "unavailable",
    }
    _, body = inbox("ai_setup", data, "ar")
    assert "الشرح غير متاح" in body and "التقييم" not in body  # no grade line in v1
    _, body = inbox("ai_setup", {**data, "explanation": "Template: buy"}, "en")
    assert "Template: buy" in body and "Explanation unavailable" not in body
