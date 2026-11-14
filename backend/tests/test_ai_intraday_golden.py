"""B13 golden test: the ``intraday`` profile is byte-identical to before contract 0.3.0.

A whole intraday life cycle (DEVELOPING, ARMED, ACTIVE, CLOSED) against the fake ai-service
without the new ``volatility`` field, with calendar events around the bars. Everything the
backend sends and keeps is compared with ``fixtures/ai_intraday_golden.json``, recorded by this
same test on ``main`` before B13 (``GOLDEN_WRITE=<path>`` writes the file instead of comparing):

- every ``/v1/evaluate`` request body, byte for byte (bars, spreads, calendar, the echo of
  ``open_setups``, ``instrument_spec``), and the answer it got;
- what was stored: the run rows (status, reason, coverage, the summary of the answer), the
  setups, their events and the alerts' outbox rows;
- the alert data and its Arabic and English texts (the instrument id masked).

The calendar has a USD high event of the same New York day but outside ±6 h of every bar
**after** 16:45 New York, so B13's day window does not add it either.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.ai import alerts, evaluate
from app.ai.client import AIServiceClient
from app.calendar import service as calendar_service
from app.calendar.events import EventIn
from app.core.config import get_settings
from app.models.ai import AIEvaluationRun, AISetup, AISetupEvent, AISetupOutbox
from app.models.instrument import Instrument, MarketType
from app.notifications import templates
from tests.market_utils import make_instrument
from tests.test_ai_evaluate import CLOSE, GOLD, M15, SMALL, After, fake, history

FIXTURE = Path(__file__).parent / "fixtures" / "ai_intraday_golden.json"


class Recording(httpx.AsyncBaseTransport):
    """The fake in-process, keeping every request body as sent."""

    def __init__(self) -> None:
        self.inner = httpx.ASGITransport(app=fake.app)
        self.bodies: list[bytes] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/evaluate":
            self.bodies.append(request.content)
        return await self.inner.handle_async_request(request)


def _event(title: str, at: datetime, impact: str, currency: str = "USD") -> EventIn:
    return EventIn.build(
        source="forexfactory_live", currency=currency, title=title, impact=impact, scheduled_at=at
    )


def _iso(value) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


@pytest.fixture(autouse=True)
async def _clean(redis_client):
    async def clean() -> None:
        keys = [k async for k in redis_client.scan_iter(match="ai:evaluate:*")]
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
    monkeypatch.setattr(s, "ai_profiles", "intraday")
    for name, value in SMALL.items():
        monkeypatch.setattr(s, name, value)
    return s


@pytest.fixture
async def gold(session) -> Instrument:
    return await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity, **GOLD)


async def test_intraday_is_byte_identical(session, session_factory, redis_client, gold, settings):
    fake.STATE.modes["volatility"] = "off"  # an answer as before 0.3.0 (ignored by old fakes)
    await calendar_service.upsert_versions(
        session,
        [
            _event("CPI m/m", CLOSE - timedelta(minutes=45), "high"),  # 09:30 New York
            _event("Retail Sales", CLOSE + timedelta(hours=1), "medium"),
            _event("Bund Auction", CLOSE + timedelta(hours=2), "medium", "EUR"),
            _event("Fed Speech", CLOSE + timedelta(hours=8), "high"),  # 18:15 New York
            _event("Overnight PMI", CLOSE - timedelta(hours=9), "medium"),
        ],
        CLOSE - timedelta(days=3),
    )
    await history(session, gold, CLOSE + 3 * M15)
    after = After()
    transport = Recording()
    client = AIServiceClient("http://fake", transport=transport, backoff=0)
    for k in range(4):
        close = CLOSE + k * M15
        result = await evaluate.run(
            session_factory, redis_client, "fxpro", "XAU/USD", "intraday", close,
            now=close + timedelta(seconds=20), client=client, kick=after.kick,
            schedule_explain=after.explain,
        )  # fmt: skip
        assert result.status == "ok", result.detail
    await client.aclose()

    runs = (await session.scalars(select(AIEvaluationRun).order_by(AIEvaluationRun.id))).all()
    setups = (await session.scalars(select(AISetup).order_by(AISetup.setup_id))).all()
    events = (
        await session.scalars(select(AISetupEvent).order_by(AISetupEvent.at, AISetupEvent.id))
    ).all()
    outbox = (await session.scalars(select(AISetupOutbox).order_by(AISetupOutbox.id))).all()
    instrument_id = str(gold.id)

    def mask(value):
        return json.loads(json.dumps(value, default=str).replace(instrument_id, "<instrument>"))

    alert_data = []
    for row in outbox:
        setup = next(s for s in setups if s.setup_id == row.setup_id)
        data = mask(alerts._base_data(row, setup, gold, late=False))
        texts = {lang: list(templates.inbox("ai_setup", data, lang)) for lang in ("ar", "en")}
        alert_data.append({"data": data, "texts": texts, "frame": alerts._frame(row, setup)})
    got = {
        "requests": [body.decode() for body in transport.bodies],
        "responses": [answer.decode() for answer in fake.STATE.answers.values()],
        "runs": [
            {
                "bar_close_ts": _iso(r.bar_close_ts),
                "request_id": r.request_id,
                "status": r.status,
                "reason": r.reason,
                "request_bytes": r.request_bytes,
                "coverage": r.coverage,
                "detail": r.detail,
            }
            for r in runs
        ],
        "setups": [
            {
                name: _iso(value) if isinstance(value, datetime) else value
                for name, value in (
                    (c, getattr(s, c))
                    for c in (
                        "setup_id",
                        "profile",
                        "direction",
                        "state",
                        "entry",
                        "sl",
                        "tp",
                        "r_multiple",
                        "probability",
                        "ev_r",
                        "ev_r_lower",
                        "grade",
                        "valid_until",
                        "horizon_until",
                        "realized_r",
                        "evidence",
                        "features",
                        "last_payload",
                        "strategy_version",
                        "model_version",
                        "features_version",
                        "first_request_id",
                        "last_request_id",
                    )
                )
            }
            for s in setups
        ],  # fmt: skip
        "events": [
            [e.setup_id, e.from_state, e.to_state, _iso(e.at), e.reason, e.realized_r, e.request_id]
            for e in events
        ],  # fmt: skip
        "outbox": [
            [o.setup_id, o.from_state, o.to_state, _iso(o.at), o.reason, o.realized_r]
            for o in outbox
        ],
        "alerts": mask(alert_data),
        "explains": after.explains,
    }
    if os.environ.get("GOLDEN_WRITE"):
        Path(os.environ["GOLDEN_WRITE"]).write_text(
            json.dumps(got, indent=1, ensure_ascii=False, sort_keys=True) + "\n", "utf-8"
        )
        pytest.skip("golden file written")
    expected = json.loads(FIXTURE.read_text("utf-8"))
    got = json.loads(json.dumps(got, sort_keys=True))
    for key in sorted(expected):
        assert got[key] == expected[key], key
    assert sorted(got) == sorted(expected)
    # byte for byte, not only equal JSON: the bodies as sent
    assert got["requests"] == expected["requests"]
    assert len(got["requests"]) == 4
