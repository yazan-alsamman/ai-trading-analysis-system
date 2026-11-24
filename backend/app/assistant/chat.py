"""The AI assistant chat (docs/ai-chat.md): Gemini text answers with the platform's market
context.

- Stateless: the app sends the conversation (at most 20 turns) with every question; nothing
  of the conversation is stored. Only a log line with the token usage.
- The system instruction is the versioned prompt ``prompts/<PROMPT_VERSION>.md``; the market
  context (latest price and 24 h change, news sentiment and headlines, upcoming high-impact
  economic events) is built from the database at each question and sent as a separate text
  block, so the model never has to invent numbers. Every part of the context is optional: a
  failing part is left out.
- A daily quota per user and role in Redis (``AI_CHAT_DAILY_LIMIT_<ROLE>``); a failed model call
  gives its unit back.
- Errors never become a 500: 503 ``not_configured`` (no key / feature off), 503 ``model_busy`` /
  ``model_unavailable`` / ``timeout`` with Retry-After, 422 ``blocked`` / ``empty_answer``.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.user import User

logger = logging.getLogger(__name__)

PROMPT_VERSION = "assistant_v1"
PROMPTS = Path(__file__).parent / "prompts"
QUOTA_PREFIX = "aichat:quota:"
RETRIES = 1
BACKOFF_SECONDS = 1.5
RETRY_AFTER_SECONDS = 30
TEMPERATURE = 0.4
LANGUAGE_NAMES = {"ar": "Arabic", "en": "English"}
OK_FINISH = {"STOP", "FINISH_REASON_UNSPECIFIED", "MAX_TOKENS"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def _error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    headers = None
    if (retry := extra.pop("retry_after", None)) is not None:
        headers = {"Retry-After": str(int(retry))}
    return HTTPException(status_code, {"code": code, "message": message, **extra}, headers)


@lru_cache
def prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"{version}.md").read_text(encoding="utf-8")


def model_name() -> str:
    settings = get_settings()
    return settings.ai_chat_model.strip() or settings.chart_vision_model


def configured() -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        return False, "AI_CHAT_ENABLED=false"
    if not settings.gemini_api_key.strip():
        return False, "GEMINI_API_KEY is not set"
    return True, None


def require_enabled() -> None:
    enabled, reason = configured()
    if not enabled:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "not_configured",
            "the AI assistant is not configured",
            reason=reason,
        )


_client: Any = None
_client_key: str | None = None


def get_client() -> Any:
    """The process's ``genai.Client`` for the chat (created on first use, never without a
    key)."""
    global _client, _client_key
    require_enabled()
    settings = get_settings()
    key = settings.gemini_api_key.strip()
    if _client is None or _client_key != key:
        from google import genai  # noqa: PLC0415 - loaded only when the feature is used
        from google.genai import types  # noqa: PLC0415

        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=int(settings.ai_chat_timeout_seconds * 1000),
                base_url=settings.chart_vision_base_url or None,
            ),
        )
        _client_key = key
    return _client


# --- quota ---------------------------------------------------------------------------------------


def daily_limit(user: User) -> int:
    return int(getattr(get_settings(), f"ai_chat_daily_limit_{user.role.value}"))


def _day_key(user_id: uuid.UUID, now: datetime) -> str:
    return f"{QUOTA_PREFIX}{user_id}:{now:%Y%m%d}"


def _reset_at(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)


async def quota(redis: Redis, user: User) -> dict[str, Any]:
    now = utcnow()
    used = int(await redis.get(_day_key(user.id, now)) or 0)
    limit = daily_limit(user)
    return {
        "limit": limit,
        "used": min(used, limit),
        "remaining": max(0, limit - used),
        "resets_at": _reset_at(now),
    }


async def _take_quota(redis: Redis, user: User) -> str:
    now = utcnow()
    key, limit = _day_key(user.id, now), daily_limit(user)
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 2 * 86400)
    if used > limit:
        await redis.decr(key)
        retry = max(1, int((_reset_at(now) - now).total_seconds()))
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "quota_exceeded",
            f"daily limit of {limit} assistant questions reached",
            retry_after=retry,
            limit=limit,
            resets_at=_reset_at(now).isoformat(),
        )
    return key


async def _give_back(redis: Redis, key: str) -> None:
    try:
        await redis.decr(key)
    except Exception:  # noqa: BLE001
        logger.warning("ai chat: could not give a quota unit back")


# --- market context ------------------------------------------------------------------------------


async def _instrument(session: AsyncSession, instrument_id: uuid.UUID | None) -> Instrument | None:
    if instrument_id is not None:
        instrument = await session.get(Instrument, instrument_id)
        if instrument is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
        return instrument
    key = get_settings().ctrader_instrument_key
    if key is None:
        return None
    source, symbol = key
    return await session.scalar(
        select(Instrument).where(Instrument.source == source, Instrument.symbol == symbol)
    )


def _fmt(value: float | None, digits: int) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


async def _price_lines(session: AsyncSession, instrument: Instrument) -> list[str]:
    from app.services import market_service  # noqa: PLC0415

    digits = instrument.price_precision if instrument.price_precision is not None else 2
    latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    if latest is None:
        return [f"{instrument.symbol}: no price data available."]
    line = (
        f"{instrument.symbol} latest price {_fmt(latest.close, digits)} "
        f"(1m candle of {latest.ts:%Y-%m-%d %H:%M} UTC)"
    )
    try:
        hourly = await market_service.get_candles(session, instrument.id, Timeframe.h1, limit=25)
    except Exception:  # noqa: BLE001 - the 24 h figures are optional
        logger.warning("ai chat: no hourly candles for the context", exc_info=True)
        hourly = []
    if len(hourly) >= 2 and hourly[0].close:
        change = (latest.close - hourly[0].close) / hourly[0].close * 100
        high = max(c.high for c in hourly)
        low = min(c.low for c in hourly)
        line += (
            f"; about 24 h change {change:+.2f}%; 24 h range {_fmt(low, digits)} - "
            f"{_fmt(high, digits)}"
        )
    age = utcnow() - latest.ts
    if age > timedelta(minutes=30):
        line += " (the market looks closed: this is the last known price)"
    return [line + "."]


async def _news_lines(session: AsyncSession, instrument: Instrument | None) -> list[str]:
    from app.news import service as news  # noqa: PLC0415

    iid = instrument.id if instrument is not None else None
    lines: list[str] = []
    agg = await news.sentiment_aggregate(session, "24h", iid)
    bucket = agg["overall"]
    if iid is not None:
        bucket = next((i for i in agg["instruments"] if i["instrument_id"] == iid), bucket)
    if bucket and bucket.get("articles"):
        score = bucket.get("weighted_score") or bucket.get("mean_score")
        lines.append(
            "News sentiment, last 24 h (FinBERT): "
            f"{bucket['articles']} articles, {bucket.get('positive', 0)} positive, "
            f"{bucket.get('neutral', 0)} neutral, {bucket.get('negative', 0)} negative"
            + (f", mean score {score:+.2f} (-1..1)" if score is not None else "")
            + "."
        )
    items, _ = await news.list_articles(session, limit=5, offset=0, instrument_id=iid)
    for item in items:
        label = (item.get("sentiment") or {}).get("label")
        lines.append(
            f"- Headline ({item['published_at']:%Y-%m-%d %H:%M} UTC, {item['source']['name']}"
            + (f", {label}" if label else "")
            + f"): {item['title'][:200]}"
        )
    return lines


async def _calendar_lines(session: AsyncSession) -> list[str]:
    from app.calendar import service as calendar  # noqa: PLC0415

    now = utcnow()
    events = await calendar.latest_as_of(
        session, now, now + timedelta(hours=48), currencies=["USD"], min_impact="high"
    )
    lines = []
    for event in events[:6]:
        when = f"{event.scheduled_at:%Y-%m-%d %H:%M} UTC" if event.scheduled_at else "time n/a"
        extra = []
        if event.forecast:
            extra.append(f"forecast {event.forecast}")
        if event.previous:
            extra.append(f"previous {event.previous}")
        lines.append(
            f"- {when}: {event.currency} {event.title} (high impact"
            + (", " + ", ".join(extra) if extra else "")
            + ")"
        )
    return (["Upcoming high-impact USD events (next 48 h):", *lines]) if lines else []


async def build_context(
    session: AsyncSession, language: str, instrument_id: uuid.UUID | None
) -> str:
    instrument = await _instrument(session, instrument_id)
    parts = [
        f"Platform context (generated {utcnow():%Y-%m-%d %H:%M} UTC).",
        f"Answer language: {LANGUAGE_NAMES[language]}.",
    ]
    builders = []
    if instrument is not None:
        builders.append(("price", lambda: _price_lines(session, instrument)))
    builders.append(("news", lambda: _news_lines(session, instrument)))
    builders.append(("calendar", lambda: _calendar_lines(session)))
    for name, build in builders:
        try:
            # a savepoint: a failing query does not abort the other parts
            async with session.begin_nested():
                parts.extend(await build())
        except Exception:  # noqa: BLE001 - context is best effort, never fails the question
            logger.warning("ai chat: the %s context could not be built", name, exc_info=True)
    return "\n".join(parts)


# --- the model call ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatAnswer:
    reply: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def _name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _text(response: Any) -> str:
    feedback = getattr(response, "prompt_feedback", None)
    blocked = _name(getattr(feedback, "block_reason", None)) if feedback else None
    if blocked and blocked != "BLOCKED_REASON_UNSPECIFIED":
        raise _error(422, "blocked", f"the model blocked the question ({blocked})")
    candidates = getattr(response, "candidates", None) or []
    finish = _name(getattr(candidates[0], "finish_reason", None)) if candidates else None
    if finish and finish not in OK_FINISH:
        raise _error(422, "blocked", f"the model stopped without an answer ({finish})")
    try:
        text = getattr(response, "text", None)
    except Exception:  # noqa: BLE001 - the SDK raises when there is no text part
        text = None
    text = (text or "").strip()
    if not text:
        raise _error(422, "empty_answer", "the model returned an empty answer")
    return text


def _usage(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None
    answer = getattr(usage, "candidates_token_count", None)
    thoughts = getattr(usage, "thoughts_token_count", None)
    output = None if answer is None and thoughts is None else (answer or 0) + (thoughts or 0)
    return getattr(usage, "prompt_token_count", None), output


def _unavailable(code: str, message: str) -> HTTPException:
    return _error(
        status.HTTP_503_SERVICE_UNAVAILABLE, code, message, retry_after=RETRY_AFTER_SECONDS
    )


async def ask(messages: list[dict[str, str]], context: str, *, client: Any = None) -> ChatAnswer:
    from google.genai import errors, types  # noqa: PLC0415

    settings = get_settings()
    client = client or get_client()
    model = model_name()
    config = types.GenerateContentConfig(
        temperature=TEMPERATURE,
        max_output_tokens=settings.ai_chat_max_output_tokens,
        system_instruction=prompt(),
    )
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=context)]),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="Understood. I will use only this context.")],
        ),
    ]
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    started = time.monotonic()
    deadline = started + settings.ai_chat_timeout_seconds
    response, attempt = None, 0
    while response is None:
        attempt += 1
        left = deadline - time.monotonic()
        if left <= 0:
            raise _unavailable("timeout", "the assistant did not answer in time, try again later")
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=left,
            )
        except TimeoutError:
            raise _unavailable(
                "timeout", "the assistant did not answer in time, try again later"
            ) from None
        except errors.APIError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            if code in (401, 403):
                logger.error("ai chat: the Gemini key was refused (%s)", code)
                raise _unavailable(
                    "not_configured", "the assistant is unavailable (the model refused the key)"
                ) from None
            if code != 429 and code < 500:
                logger.warning("ai chat: %s rejected the request (%s)", model, code)
                raise _error(
                    422, "could_not_answer", f"the model rejected the question ({code})"
                ) from None
            if attempt > RETRIES:
                raise _unavailable(
                    "model_busy" if code == 429 else "model_unavailable",
                    "the assistant is busy, try again later",
                ) from None
        except (httpx.HTTPError, OSError):
            if attempt > RETRIES:
                raise _unavailable(
                    "model_unavailable", "the assistant is unavailable, try again later"
                ) from None
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001 - anything unexpected from the SDK: never a 500
            logger.exception("ai chat: unexpected error from %s", model)
            raise _unavailable(
                "model_unavailable", "the assistant is unavailable, try again later"
            ) from None
        if response is None:
            await asyncio.sleep(max(0.0, min(BACKOFF_SECONDS, deadline - time.monotonic())))
    latency_ms = round((time.monotonic() - started) * 1000)
    tokens_in, tokens_out = _usage(response)
    reply = _text(response)
    logger.info(
        "ai chat model=%s tokens_in=%s tokens_out=%s latency_ms=%d attempts=%d",
        model, tokens_in, tokens_out, latency_ms, attempt,
    )  # fmt: skip
    return ChatAnswer(reply, model, tokens_in, tokens_out, latency_ms)


async def answer(
    session: AsyncSession,
    redis: Redis,
    user: User,
    messages: list[dict[str, str]],
    language: str,
    instrument_id: uuid.UUID | None,
    *,
    client: Any = None,
) -> dict[str, Any]:
    require_enabled()
    context = await build_context(session, language, instrument_id)
    key = await _take_quota(redis, user)
    try:
        result = await ask(messages, context, client=client)
    except HTTPException as exc:
        if exc.status_code >= 500 or (
            isinstance(exc.detail, dict) and exc.detail.get("code") == "blocked"
        ):
            await _give_back(redis, key)
        raise
    except BaseException:
        await _give_back(redis, key)
        raise
    return {
        "reply": result.reply,
        "language": language,
        "model": result.model,
        "usage": {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        },
        "quota": await quota(redis, user),
        "disclaimer": DISCLAIMERS[language],
    }


DISCLAIMERS = {
    "ar": "هذه معلومات تعليمية وليست نصيحة استثمارية. تداول فقط بما تستطيع تحمل خسارته.",
    "en": "Educational information, not investment advice. Only trade what you can afford to lose.",
}
