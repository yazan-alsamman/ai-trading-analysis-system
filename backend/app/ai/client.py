"""The ai-service client (B7, docs/ai-contract.md).

- One timeout per attempt and endpoint (``AI_*_TIMEOUT_SECONDS``).
- Timeouts, connection errors and 5xx are retried ``AI_MAX_RETRIES`` times with exponential
  backoff and jitter, always with the same body (so the same ``request_id``): ai-service is
  stateless and deterministic, a retry cannot create a second result.
- 422 (and any other 4xx) is never retried: ``AIContractError`` with ai-service's detail. A
  200 whose body does not match the contract is an ``AIContractError`` too.
- After the last attempt: ``AIUnavailableError``.
- Every attempt logs the request id, attempt, status and latency, never the payloads (an
  evaluate request carries ~1,300 bars).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.contract import (
    EvaluateRequest,
    EvaluateResponse,
    ExplainRequest,
    ExplainResponse,
    SizeRequest,
    SizeResponse,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

R = TypeVar("R", bound=BaseModel)
BACKOFF_SECONDS = 0.5  # first retry after ~0.5 s, then ~1 s (plus up to 50 % jitter)


class AIServiceError(Exception):
    """Base of the client errors."""


class AIContractError(AIServiceError):
    """ai-service refused the request (422 / 4xx) or answered outside the contract. Retrying
    the same request cannot help."""

    def __init__(self, message: str, *, status: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class AIUnavailableError(AIServiceError):
    """No usable answer after every attempt (timeouts, connection errors, 5xx)."""

    def __init__(self, message: str, *, attempts: int, last_error: str) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class AIServiceClient:
    """``async with AIServiceClient() as ai: await ai.evaluate(req)``. Tests pass a
    ``transport`` (no network) and ``backoff=0``."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int | None = None,
        backoff: float = BACKOFF_SECONDS,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")
        self.max_retries = settings.ai_max_retries if max_retries is None else max_retries
        self.backoff = backoff
        self._client = httpx.AsyncClient(base_url=self.base_url, transport=transport)

    async def __aenter__(self) -> AIServiceClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def evaluate(self, req: EvaluateRequest) -> EvaluateResponse:
        resp = await self._call(
            "/v1/evaluate",
            req,
            EvaluateResponse,
            req.request_id,
            get_settings().ai_evaluate_timeout_seconds,
        )
        if resp.request_id != req.request_id:
            raise AIContractError(
                f"response request_id {resp.request_id!r} is not {req.request_id!r}"
            )
        return resp

    async def size(self, req: SizeRequest) -> SizeResponse:
        return await self._call(
            "/v1/size",
            req,
            SizeResponse,
            req.setup.setup_id,
            get_settings().ai_size_timeout_seconds,
        )

    async def explain(self, req: ExplainRequest) -> ExplainResponse:
        return await self._call(
            "/v1/explain",
            req,
            ExplainResponse,
            req.setup.setup_id,
            get_settings().ai_explain_timeout_seconds,
        )

    async def _call(
        self, path: str, req: BaseModel, model: type[R], request_id: str, timeout: float
    ) -> R:
        # serialised once: every attempt sends exactly the same bytes
        content = json.dumps(req.model_dump(mode="json", by_alias=True)).encode()
        headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
        attempts = self.max_retries + 1
        last_error = ""
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            status: int | str
            try:
                response = await self._client.post(
                    path, content=content, headers=headers, timeout=timeout
                )
                status = response.status_code
            except httpx.TimeoutException:
                status, response = "timeout", None
            except httpx.TransportError as exc:
                status, response = f"connection error ({type(exc).__name__})", None
            latency = (time.perf_counter() - started) * 1000
            logger.info(
                "ai-service %s request_id=%s attempt=%d/%d status=%s latency_ms=%.0f",
                path,
                request_id,
                attempt,
                attempts,
                status,
                latency,
            )
            if response is not None and response.status_code == 200:
                return self._parse(path, response, model)
            if response is not None and response.status_code < 500:
                raise AIContractError(
                    f"ai-service {path} answered {response.status_code}",
                    status=response.status_code,
                    detail=_detail(response),
                )
            last_error = str(status)
            if attempt < attempts:
                await asyncio.sleep(self._delay(attempt))
        logger.warning(
            "ai-service %s request_id=%s unavailable after %d attempts (%s)",
            path,
            request_id,
            attempts,
            last_error,
        )
        raise AIUnavailableError(
            f"ai-service {path} unavailable after {attempts} attempts: {last_error}",
            attempts=attempts,
            last_error=last_error,
        )

    def _delay(self, attempt: int) -> float:
        base = self.backoff * 2 ** (attempt - 1)
        return base + random.uniform(0, base / 2)  # noqa: S311 - jitter, not security

    @staticmethod
    def _parse(path: str, response: httpx.Response, model: type[R]) -> R:
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else str(exc)
            raise AIContractError(
                f"ai-service {path}: the response does not match the contract",
                status=200,
                detail=errors,
            ) from None


def _detail(response: httpx.Response) -> Any:
    try:
        return response.json().get("detail")
    except (ValueError, AttributeError):
        return response.text[:500]
