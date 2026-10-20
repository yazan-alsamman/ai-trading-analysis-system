"""The ForexFactory weekly calendar (JSON, public, no key): one polite request per run.

The host rate-limits or blocks clients that poll too often: one GET with a clear User-Agent,
a deadline for the whole request, a size cap, a conditional GET (ETag), and a 429/403 raises
``Blocked`` so the caller backs off. The payload is checked at runtime: a body that is not a
list fails the fetch, an item that does not validate is skipped (the others are kept).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.calendar.events import EventIn
from app.core.config import get_settings
from app.models.economic_event import EventImpact, EventSource

logger = logging.getLogger(__name__)

USER_AGENT = (
    "AI-Trading-Platform-Calendar/1.0 (+economic calendar; one request every few hours; "
    "contact: admin)"
)
MAX_ITEMS = 2000  # a week has ~100
# ForexFactory's labels for events without a clock time
TIME_LABELS = {"all day", "tentative"}

transport: httpx.AsyncBaseTransport | None = None  # tests inject a mock transport


class FetchError(Exception):
    """The fetch failed (timeout, HTTP error, oversize or unexpected body)."""


class Blocked(FetchError):
    """429 or 403: the host asks us to go away for a while."""

    def __init__(self, status: int, retry_after: str | None = None) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.retry_after = retry_after


class FFItem(BaseModel):
    """One item of ff_calendar_thisweek.json. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str
    country: str
    date: str
    impact: str
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None
    time: str | None = None  # not in today's JSON; the XML/other exports carry "All Day" etc.

    @field_validator("title", "country", "date", "impact")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value:
            raise ValueError("empty")
        return value


def normalise(item: FFItem) -> EventIn:
    """``date`` (ISO with its offset) to UTC, ``country`` to the currency, the impact in lower
    case. A day without a time, or an "All Day"/"Tentative" label, has no ``scheduled_at``."""
    impact = item.impact.strip().lower()
    if impact not in {i.value for i in EventImpact}:
        raise ValueError(f"unknown impact {item.impact!r}")
    label = (item.time or "").strip()
    raw = item.date.strip()
    if len(raw) == 10:  # a bare day
        return EventIn.build(
            source=EventSource.forexfactory_live,
            currency=item.country,
            title=item.title,
            impact=impact,
            scheduled_at=None,
            scheduled_date=date.fromisoformat(raw),
            time_label=label or "All Day",
            actual=item.actual,
            forecast=item.forecast,
            previous=item.previous,
        )
    moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"date without an offset: {raw!r}")
    if label.lower() in TIME_LABELS or (label and not label[0].isdigit()):
        return EventIn.build(
            source=EventSource.forexfactory_live,
            currency=item.country,
            title=item.title,
            impact=impact,
            scheduled_at=None,
            scheduled_date=moment.date(),  # the day as published (New York)
            time_label=label,
            actual=item.actual,
            forecast=item.forecast,
            previous=item.previous,
        )
    return EventIn.build(
        source=EventSource.forexfactory_live,
        currency=item.country,
        title=item.title,
        impact=impact,
        scheduled_at=moment,
        actual=item.actual,
        forecast=item.forecast,
        previous=item.previous,
    )


@dataclass
class Week:
    status: str  # ok | not_modified
    events: list[EventIn] = field(default_factory=list)
    items: int = 0
    skipped: list[str] = field(default_factory=list)  # why, per skipped item
    etag: str | None = None
    size: int = 0


def parse(body: bytes) -> Week:
    """Events from a response body. Raises FetchError when the body is not a JSON list."""
    try:
        payload = json.loads(body)
    except ValueError:
        raise FetchError("body is not JSON") from None
    if not isinstance(payload, list):
        raise FetchError(f"unexpected shape: a {type(payload).__name__}, not a list")
    week = Week("ok", items=len(payload), size=len(body))
    for index, raw in enumerate(payload[:MAX_ITEMS]):
        try:
            if not isinstance(raw, dict):
                raise ValueError("not an object")
            week.events.append(normalise(FFItem.model_validate(raw)))
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                reason = ", ".join(
                    f"{'.'.join(map(str, e['loc'])) or 'item'}: {e['msg']}" for e in exc.errors()
                )
            else:
                reason = str(exc)
            week.skipped.append(f"item {index}: {reason}"[:200])
    if week.skipped:
        logger.warning(
            "calendar: %d of %d items skipped (first: %s)",
            len(week.skipped),
            week.items,
            week.skipped[0],
        )
    return week


async def fetch_week(client: httpx.AsyncClient | None = None, *, etag: str | None = None) -> Week:
    """One GET of ``CALENDAR_FF_URL``. Raises Blocked on 429/403 and FetchError otherwise."""
    settings = get_settings()
    if client is None:
        async with httpx.AsyncClient(  # nosec B113 - the deadline is the asyncio.timeout below
            transport=transport, follow_redirects=True, max_redirects=3, timeout=None
        ) as own:
            return await fetch_week(own, etag=etag)
    limit = settings.calendar_fetch_max_bytes
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    try:
        # one deadline for the whole request: a server dripping bytes cannot hold the task
        async with asyncio.timeout(settings.calendar_fetch_timeout_seconds):
            async with client.stream("GET", settings.calendar_ff_url, headers=headers) as response:
                if response.status_code == 304:
                    return Week("not_modified", etag=etag)
                if response.status_code in (403, 429):
                    raise Blocked(response.status_code, response.headers.get("retry-after"))
                if response.status_code != 200:
                    raise FetchError(f"HTTP {response.status_code}")
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > limit:
                    raise FetchError(f"body larger than {limit} bytes")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > limit:
                        raise FetchError(f"body larger than {limit} bytes")
                new_etag = response.headers.get("etag") or None
    except TimeoutError:
        raise FetchError(f"timeout after {settings.calendar_fetch_timeout_seconds:g}s") from None
    except httpx.HTTPError as exc:
        raise FetchError(type(exc).__name__) from None
    week = parse(bytes(body))
    week.etag = new_etag
    return week
