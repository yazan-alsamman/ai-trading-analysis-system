"""The Gemini call of the chart analysis (Y14, docs/chart-analysis.md).

- The official ``google-genai`` SDK, asynchronously (``client.aio``), so an API worker is never
  blocked while the model answers. One client per process, created on first use and only when
  ``GEMINI_API_KEY`` is set. The SDK's own retries are off: this module retries itself.
- The image goes first (``Part.from_bytes``), then the request text. Structured output only:
  ``response_mime_type=application/json`` with ``response_schema=ModelChartAnalysis``, and
  ``response.parsed`` is validated again with Pydantic. Free text is never parsed.
- The system instruction is the versioned prompt ``prompts/<PROMPT_VERSION>.md``.

Errors never become a 500:

- a blocked prompt, a safety (or other) finish, an empty or invalid ``parsed``, or a 4xx from
  the model: :class:`VisionRefused`, 422 ``could_not_analyse``;
- 429 or 5xx after at most 2 retries with backoff, or a network error:
  :class:`VisionUnavailable`, 503 + Retry-After;
- no answer within ``CHART_VISION_TIMEOUT_SECONDS`` (all attempts included):
  :class:`VisionUnavailable` ``timeout``, 503 + Retry-After;
- no key or the feature turned off: :class:`VisionNotConfigured`, 503; the key refused
  (401/403): 503 ``not_configured``.

Logged: model, token usage, latency, attempts, ``is_chart``. Never the image, its base64 or the
key.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.vision.images import PreparedImage
from app.vision.schemas import ModelChartAnalysis

logger = logging.getLogger(__name__)

PROMPT_VERSION = "chart_v1"
PROMPTS = Path(__file__).parent / "prompts"
RETRIES = 2  # after the first attempt, for 429 / 5xx / network errors
BACKOFF_SECONDS = (1.0, 3.0)
RETRY_AFTER_SECONDS = 30
TEMPERATURE = 0.2
LANGUAGE_NAMES = {"ar": "Arabic", "en": "English"}
# finish reasons that still carry a usable answer
OK_FINISH = {"STOP", "FINISH_REASON_UNSPECIFIED", "MAX_TOKENS"}


class VisionError(Exception):
    status = 503
    code = "unavailable"

    def __init__(self, message: str, *, code: str | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.retry_after = retry_after


class VisionNotConfigured(VisionError):
    code = "not_configured"


class VisionUnavailable(VisionError):
    code = "model_unavailable"


class VisionRefused(VisionError):
    status = 422
    code = "could_not_analyse"


@dataclass(frozen=True)
class VisionResult:
    analysis: ModelChartAnalysis
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    attempts: int


@lru_cache
def prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"{version}.md").read_text(encoding="utf-8")


def configured() -> tuple[bool, str | None]:
    """(enabled, why not). Disabled is a normal state, not an error."""
    settings = get_settings()
    if not settings.chart_analysis_enabled:
        return False, "CHART_ANALYSIS_ENABLED=false"
    if not settings.gemini_api_key.strip():
        return False, "GEMINI_API_KEY is not set"
    return True, None


_client: Any = None
_client_key: str | None = None


def get_client() -> Any:
    """The process's ``genai.Client``, created on first use (never without a key)."""
    global _client, _client_key
    enabled, reason = configured()
    if not enabled:
        raise VisionNotConfigured(f"chart analysis is not configured ({reason})")
    key = get_settings().gemini_api_key.strip()
    if _client is None or _client_key != key:
        from google import genai  # noqa: PLC0415 - loaded only when the feature is used
        from google.genai import types  # noqa: PLC0415

        settings = get_settings()
        _client = genai.Client(
            api_key=key,
            # one attempt per call from the SDK; the per-attempt cap is the whole timeout
            http_options=types.HttpOptions(
                timeout=int(settings.chart_vision_timeout_seconds * 1000),
                base_url=settings.chart_vision_base_url or None,
            ),
        )
        _client_key = key
    return _client


def _request_text(language: str, symbol: str | None, timeframe: str | None) -> str:
    lines = [
        f"Requested language: {language} ({LANGUAGE_NAMES[language]}). Write every text field "
        f"in {LANGUAGE_NAMES[language]}."
    ]
    if symbol or timeframe:
        lines.append(
            "Hints from the user (may be wrong; the image wins): "
            f"symbol={symbol or 'unknown'}, timeframe={timeframe or 'unknown'}."
        )
    lines.append("Analyse the chart image above and answer with the JSON object only.")
    return "\n".join(lines)


def _name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _parse(response: Any) -> ModelChartAnalysis:
    """The validated answer, or :class:`VisionRefused` (blocked, safety, empty, invalid)."""
    feedback = getattr(response, "prompt_feedback", None)
    blocked = _name(getattr(feedback, "block_reason", None)) if feedback else None
    if blocked and blocked != "BLOCKED_REASON_UNSPECIFIED":
        raise VisionRefused(f"the model blocked the request ({blocked})", code="blocked")
    candidates = getattr(response, "candidates", None) or []
    finish = _name(getattr(candidates[0], "finish_reason", None)) if candidates else None
    if finish and finish not in OK_FINISH:
        raise VisionRefused(f"the model stopped without an answer ({finish})", code="blocked")
    parsed = getattr(response, "parsed", None)
    if parsed is None:
        raise VisionRefused("the model returned no structured answer", code="empty_answer")
    try:
        data = parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
        return ModelChartAnalysis.model_validate(data)
    except ValidationError as exc:
        raise VisionRefused(
            f"the model's answer did not match the schema ({exc.error_count()} errors)",
            code="invalid_answer",
        ) from None


def _usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None, None
    # output = the answer and the model's thinking: both are billed as output tokens
    answer = getattr(usage, "candidates_token_count", None)
    thoughts = getattr(usage, "thoughts_token_count", None)
    output = None if answer is None and thoughts is None else (answer or 0) + (thoughts or 0)
    return (
        getattr(usage, "prompt_token_count", None),
        output,
        getattr(usage, "total_token_count", None),
    )


async def analyse(
    image: PreparedImage,
    language: str,
    symbol: str | None = None,
    timeframe: str | None = None,
    *,
    client: Any = None,
) -> VisionResult:
    """One analysis (module docstring for the error mapping)."""
    from google.genai import errors, types  # noqa: PLC0415

    settings = get_settings()
    client = client or get_client()
    model = settings.chart_vision_model
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ModelChartAnalysis,
        temperature=TEMPERATURE,
        system_instruction=prompt(),
    )
    contents = [
        types.Part.from_bytes(data=image.data, mime_type=image.mime),
        types.Part.from_text(text=_request_text(language, symbol, timeframe)),
    ]
    started = time.monotonic()
    deadline = started + settings.chart_vision_timeout_seconds
    response = None
    attempt = 0
    while response is None:
        attempt += 1
        left = deadline - time.monotonic()
        if left <= 0:
            raise _timeout(model, started)
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=left,
            )
        except TimeoutError:
            raise _timeout(model, started) from None
        except errors.APIError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            if code in (401, 403):
                logger.error("chart vision: the Gemini key was refused (%s)", code)
                raise VisionUnavailable(
                    "chart analysis is unavailable (the model refused the key)",
                    code="not_configured",
                    retry_after=RETRY_AFTER_SECONDS,
                ) from None
            if code != 429 and code < 500:
                logger.warning("chart vision: %s rejected the request (%s)", model, code)
                raise VisionRefused(f"the model rejected the image ({code})") from None
            if attempt > RETRIES:
                logger.warning(
                    "chart vision: %s answered %s after %d attempts", model, code, attempt
                )
                raise VisionUnavailable(
                    "the model is busy, try again later"
                    if code == 429
                    else "the model is unavailable, try again later",
                    code="model_busy" if code == 429 else "model_unavailable",
                    retry_after=RETRY_AFTER_SECONDS,
                ) from None
        except (httpx.HTTPError, OSError) as exc:
            if attempt > RETRIES:
                logger.warning("chart vision: network error after %d attempts: %s", attempt, exc)
                raise VisionUnavailable(
                    "the model is unavailable, try again later", retry_after=RETRY_AFTER_SECONDS
                ) from None
        except Exception:  # noqa: BLE001 - anything unexpected from the SDK: never a 500
            logger.exception("chart vision: unexpected error from %s", model)
            raise VisionUnavailable(
                "the model is unavailable, try again later", retry_after=RETRY_AFTER_SECONDS
            ) from None
        if response is None:  # retry after a backoff that fits in the deadline
            pause = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
            await asyncio.sleep(max(0.0, min(pause, deadline - time.monotonic())))
    latency_ms = round((time.monotonic() - started) * 1000)
    tokens_in, tokens_out, total = _usage(response)
    try:
        analysis = _parse(response)
    except VisionRefused as exc:
        logger.info(
            "chart vision model=%s refused=%s tokens_in=%s tokens_out=%s total=%s latency_ms=%d",
            model, exc.code, tokens_in, tokens_out, total, latency_ms,
        )  # fmt: skip
        raise
    logger.info(
        "chart vision model=%s is_chart=%s tokens_in=%s tokens_out=%s total=%s latency_ms=%d "
        "attempts=%d",
        model, analysis.is_chart, tokens_in, tokens_out, total, latency_ms, attempt,
    )  # fmt: skip
    return VisionResult(analysis, model, tokens_in, tokens_out, total, latency_ms, attempt)


def _timeout(model: str, started: float) -> VisionUnavailable:
    waited = round(time.monotonic() - started, 1)
    logger.warning("chart vision: %s timed out after %.1f s", model, waited)
    return VisionUnavailable(
        "the model did not answer in time, try again later",
        code="timeout",
        retry_after=RETRY_AFTER_SECONDS,
    )
