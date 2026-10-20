"""B7 ai-service client against a fake ai-service (a FastAPI app on the contract models, behind
a transport that can inject timeouts, connection errors and 5xx): retries with the same body,
422 never retried, contract errors, logging without payloads. No network."""

import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.ai import contract as c
from app.ai.client import AIContractError, AIServiceClient, AIUnavailableError

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api" / "ai-service-examples"
LOGGER = "app.ai.client"


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


class FakeAI(httpx.AsyncBaseTransport):
    """ai-service as a FastAPI app; ``faults`` are consumed one per request first."""

    def __init__(self) -> None:
        self.faults: list[str | int] = []
        self.override: dict | None = None
        self.requests: list[tuple[str, str | None, bytes]] = []
        app = FastAPI()

        @app.post("/v1/evaluate")
        def evaluate(req: c.EvaluateRequest) -> dict:
            body = self.override or load("evaluate-response-ok")
            return {**body, "request_id": body.get("request_id") and req.request_id}

        @app.post("/v1/size")
        def size(req: c.SizeRequest) -> dict:
            return load("size-response")

        @app.post("/v1/explain")
        def explain(req: c.ExplainRequest) -> dict:
            return load("explain-response")

        self.asgi = httpx.ASGITransport(app=app)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        self.requests.append((request.url.path, request.headers.get("x-request-id"), body))
        fault = self.faults.pop(0) if self.faults else None
        if fault == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if fault == "connect":
            raise httpx.ConnectError("connection refused", request=request)
        if fault == 422:
            detail = [{"loc": ["body", "bars"], "msg": "Field required", "type": "missing"}]
            return httpx.Response(422, json={"detail": detail})
        if isinstance(fault, int):
            return httpx.Response(fault, text="upstream exploded")
        return await self.asgi.handle_async_request(request)


@pytest.fixture
def fake() -> FakeAI:
    return FakeAI()


@pytest.fixture
async def ai(fake: FakeAI):
    async with AIServiceClient("http://ai-service:8001", transport=fake, backoff=0) as client:
        yield client


def request() -> c.EvaluateRequest:
    return c.EvaluateRequest.model_validate(load("evaluate-request"))


async def test_evaluate_ok(ai: AIServiceClient, fake: FakeAI, caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    resp = await ai.evaluate(request())
    assert resp.status == c.EvaluateStatus.ok and resp.request_id == request().request_id
    assert resp.new_setups[0].payload() == load("evaluate-response-ok")["new_setups"][0]
    [(path, request_id, body)] = fake.requests
    assert path == "/v1/evaluate" and request_id == "xauusd-intraday-2026-10-19T14:15:00Z"
    assert json.loads(body) == load("evaluate-request")  # the setups are echoed as received
    [line] = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert line.startswith(
        "ai-service /v1/evaluate request_id=xauusd-intraday-2026-10-19T14:15:00Z "
        "attempt=1/3 status=200 latency_ms="
    )


async def test_timeout_then_ok_sends_the_same_body(
    ai: AIServiceClient, fake: FakeAI, caplog
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    fake.faults = ["timeout"]
    resp = await ai.evaluate(request())
    assert resp.status == c.EvaluateStatus.ok
    first, second = fake.requests
    assert first == second  # same path, same X-Request-ID, byte-identical body
    lines = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert "attempt=1/3 status=timeout" in lines[0] and "attempt=2/3 status=200" in lines[1]
    assert all("bars" not in line and "2397.1" not in line for line in lines)  # no payloads


async def test_5xx_until_unavailable(ai: AIServiceClient, fake: FakeAI, caplog) -> None:
    fake.faults = [500, 500, 503]
    with pytest.raises(AIUnavailableError, match="after 3 attempts: 503") as err:
        await ai.evaluate(request())
    assert err.value.attempts == 3 and len(fake.requests) == 3
    assert len({body for _, _, body in fake.requests}) == 1
    assert "unavailable after 3 attempts" in caplog.text


async def test_connection_errors_are_retried(fake: FakeAI) -> None:
    fake.faults = ["connect", "connect"]
    async with AIServiceClient("http://x", transport=fake, backoff=0, max_retries=1) as ai:
        with pytest.raises(AIUnavailableError, match="connection error"):
            await ai.evaluate(request())
    assert len(fake.requests) == 2


async def test_422_is_never_retried(ai: AIServiceClient, fake: FakeAI) -> None:
    fake.faults = [422]
    with pytest.raises(AIContractError) as err:
        await ai.evaluate(request())
    assert err.value.status == 422 and err.value.detail[0]["loc"] == ["body", "bars"]
    assert len(fake.requests) == 1


async def test_malformed_response_is_a_contract_error(ai: AIServiceClient, fake: FakeAI) -> None:
    fake.override = {**load("evaluate-response-ok"), "status": "great"}
    with pytest.raises(AIContractError, match="does not match the contract") as err:
        await ai.evaluate(request())
    assert err.value.status == 200 and err.value.detail[0]["loc"] == ("status",)
    assert len(fake.requests) == 1  # not retried

    broken = load("evaluate-response-ok")
    broken["new_setups"][0]["sl"] = 2405.0  # wrong side for a buy
    fake.override = broken
    with pytest.raises(AIContractError):
        await ai.evaluate(request())

    fake.override = {**load("evaluate-response-ok"), "request_id": None}
    with pytest.raises(AIContractError):
        await ai.evaluate(request())


async def test_unknown_response_fields_are_accepted(ai: AIServiceClient, fake: FakeAI) -> None:
    body = load("evaluate-response-ok")
    body["took_ms"] = 41
    body["new_setups"][0]["regime"] = "trend"
    fake.override = body
    resp = await ai.evaluate(request())
    assert resp.new_setups[0].payload()["regime"] == "trend"  # kept for the echo


async def test_size_and_explain(ai: AIServiceClient, fake: FakeAI) -> None:
    size = await ai.size(c.SizeRequest.model_validate(load("size-request")))
    assert (size.lots, size.feasible) == (0.04, True)
    explained = await ai.explain(c.ExplainRequest.model_validate(load("explain-request")))
    assert explained.verified and explained.text.startswith("إعداد شراء")
    assert [r[1] for r in fake.requests] == ["xauusd-intraday-2026-10-19T14:15:00Z-buy"] * 2


async def test_timeouts_come_from_settings(fake: FakeAI, monkeypatch) -> None:
    seen: list[float] = []

    class Recorder(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            seen.append(request.extensions["timeout"]["read"])
            return await fake.handle_async_request(request)

    async with AIServiceClient("http://x", transport=Recorder(), backoff=0) as ai:
        await ai.evaluate(request())
        await ai.size(c.SizeRequest.model_validate(load("size-request")))
        await ai.explain(c.ExplainRequest.model_validate(load("explain-request")))
    assert seen == [10.0, 5.0, 30.0]
