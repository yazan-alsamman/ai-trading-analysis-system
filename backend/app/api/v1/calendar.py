"""Economic calendar (B6, docs/economic-calendar.md): point-in-time reads for every logged-in
user (or an API key with ``market:read``), the history import and the live refresh for admins."""

import io
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.api.deps import AdminUser, MarketReader, SessionDep, get_session_factory
from app.calendar import service
from app.calendar.csv_import import (
    CsvFormatError,
    ImportOptions,
    import_rows,
    parse_mapping,
    reader,
)
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.economic_event import EventImpact
from app.models.user import UserRole
from app.schemas.calendar import EventHistory, EventList, EventRead, ImportResult, RefreshResult

router = APIRouter(prefix="/calendar", tags=["calendar"])
admin_router = APIRouter(prefix="/admin/calendar", tags=["calendar"])

MAX_RANGE = timedelta(days=31)
MAX_IMPORT_BYTES = 50 * 1024 * 1024
MULTIPART_SLACK = 64 * 1024  # boundaries and part headers around the file


def _too_large() -> str:
    return f"the CSV is larger than {MAX_IMPORT_BYTES:,} bytes"


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@router.get("/events", response_model=EventList)
async def list_events(
    principal: MarketReader,
    session: SessionDep,
    start: Annotated[datetime | None, Query(description="default: today 00:00 UTC")] = None,
    end: Annotated[datetime | None, Query(description="default: start + 7 days")] = None,
    currencies: Annotated[
        str | None,
        Query(
            max_length=200,
            description="comma list (default CALENDAR_CURRENCIES, i.e. USD); ALL: every currency",
        ),
    ] = None,
    min_impact: EventImpact = EventImpact.low,
    as_of: Annotated[
        datetime | None,
        Query(description="admins only (ignored otherwise): what was known at this time"),
    ] = None,
):
    """The events scheduled between ``start`` and ``end`` (at most 31 days), sorted by time:
    per event the newest version known at ``as_of`` (default now). Events without a time
    (All Day, Tentative) are included by their New York day. Impact order: holiday < low <
    medium < high."""
    now = datetime.now(UTC)
    start = _utc(start) if start else now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = _utc(end) if end else start + timedelta(days=7)
    if end <= start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end must be after start")
    if end - start > MAX_RANGE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "at most 31 days per request")
    is_admin = principal.api_key is None and principal.user.role == UserRole.admin
    as_of = _utc(as_of) if as_of and is_admin else now
    if currencies is None:
        codes: list[str] | None = get_settings().calendar_currency_list
    elif currencies.strip().upper() == "ALL":
        codes = None
    else:
        codes = [c.strip().upper() for c in currencies.split(",") if c.strip()]
    events = await service.latest_as_of(
        session, start, end, as_of=as_of, currencies=codes, min_impact=min_impact
    )
    return EventList(
        as_of=as_of,
        start=start,
        end=end,
        currencies=codes,
        min_impact=min_impact,
        events=[EventRead.model_validate(e) for e in events],
    )


@router.get("/events/{event_key}/history", response_model=EventHistory)
async def event_history(
    event_key: Annotated[str, Path(max_length=64)],
    _: MarketReader,
    session: SessionDep,
):
    """Every stored version of an event, oldest first (revisions: time moved, actual released,
    impact changed)."""
    versions = await service.history(session, event_key)
    if not versions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return EventHistory(
        event_key=event_key, versions=[EventRead.model_validate(v) for v in versions]
    )


IMPORT_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "the CSV (UTF-8, header row first), at most 50 MB",
                        }
                    },
                }
            }
        },
    }
}


@admin_router.post("/import", response_model=ImportResult, openapi_extra=IMPORT_BODY)
async def import_history(
    request: Request,
    _: AdminUser,
    session: SessionDep,
    tz: Annotated[
        str | None,
        Query(
            description="timezone of the CSV times (e.g. America/New_York, UTC); required "
            "unless the file carries offsets"
        ),
    ] = None,
    source: Literal["forexfactory_kaggle", "manual"] = "forexfactory_kaggle",
    since: Annotated[date | None, Query(alias="from")] = date(2018, 1, 1),
    mapping: Annotated[
        str | None,
        Query(alias="map", max_length=500, description="field=Column,... e.g. title=Name"),
    ] = None,
    date_format: Annotated[str | None, Query(max_length=40)] = None,
    dry_run: bool = False,
):
    """Load calendar history from an uploaded CSV (multipart field ``file``), the same import
    as ``scripts/load_calendar_csv.py``: the file is spooled to disk by the upload parser and
    read in batches of 5,000 rows, never held in memory. Idempotent (a second upload inserts
    nothing). ``dry_run`` parses and reports without writing. 413 above 50 MB."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMPORT_BYTES + MULTIPART_SLACK:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, _too_large())
    try:
        options = ImportOptions(
            source=source,
            tz=tz,
            since=since,
            mapping=parse_mapping(mapping),
            date_format=date_format,
            dry_run=dry_run,
        )
    except CsvFormatError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    try:
        form = await request.form(max_files=1, max_fields=5)
    except MultiPartException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from None
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "send the CSV as the multipart field 'file'"
            )
        if (upload.size or 0) > MAX_IMPORT_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, _too_large())
        handle = io.TextIOWrapper(upload.file, encoding="utf-8-sig", errors="replace", newline="")
        try:
            summary = await import_rows(None if dry_run else session, reader(handle), options)
        except CsvFormatError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
        finally:
            handle.detach()  # the upload's own file is closed with the form
    finally:
        await form.close()
    return summary.as_dict()


@admin_router.post("/refresh", response_model=RefreshResult, response_model_exclude_none=True)
async def refresh_now(
    _: AdminUser,
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
):
    """Fetch the ForexFactory week now (one request), whatever the interval, and store the new
    versions. Not during a back-off after a 429/403 (``status: backoff``); ``locked`` when a
    fetch is already running."""
    return await service.refresh(factory, get_redis(), force=True)
