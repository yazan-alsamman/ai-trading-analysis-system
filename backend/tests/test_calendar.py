"""B6 economic calendar: ForexFactory normalisation, versions (event_key, content_hash, moved
times), point-in-time reads, the ``for_evaluate`` list of B9 and the read API."""

import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar import forexfactory, service
from app.calendar.events import EventIn, parse_number
from app.models.economic_event import EconomicEvent
from app.models.user import UserRole

FIXTURES = Path(__file__).parent / "fixtures"
WINTER = (FIXTURES / "ff_calendar_week_winter.json").read_bytes()
SUMMER = (FIXTURES / "ff_calendar_week_summer.json").read_bytes()
T1 = datetime(2026, 1, 4, 18, tzinfo=UTC)  # Sunday: the week is first fetched
T2 = datetime(2026, 1, 9, 13, 31, tzinfo=UTC)  # a minute after NFP


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def by_title(events, title: str):
    [found] = [e for e in events if e.title == title]
    return found


def usd(title: str, at: datetime, impact: str = "high", **values) -> EventIn:
    return EventIn.build(
        source="forexfactory_live", currency="USD", title=title, impact=impact,
        scheduled_at=at, **values,
    )  # fmt: skip


# --- normalise ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("0.3%", 0.3),
        ("-12K", -12000),
        ("1.25M", 1_250_000),
        ("-58.1B", -58_100_000_000),
        ("53.5", 53.5),
        ("1,234", 1234),
        ("", None),
        (None, None),
        ("<1.50%", None),
        ("3.5|3.6", None),
    ],
)
def test_parse_number(raw, value) -> None:
    assert parse_number(raw) == (pytest.approx(value) if value is not None else None)


def test_normalise_winter_week() -> None:
    week = forexfactory.parse(WINTER)
    assert week.items == 17 and len(week.events) == 16
    [skipped] = week.skipped
    assert skipped.startswith("item 16: date") and "Field required" in skipped

    nfp = by_title(week.events, "Non-Farm Employment Change")
    assert nfp.scheduled_at == utc(2026, 1, 9, 13, 30)  # 08:30 EST = 13:30 UTC
    assert nfp.scheduled_date == date(2026, 1, 9)
    assert (nfp.currency, nfp.impact, nfp.source) == ("USD", "high", "forexfactory_live")
    assert (nfp.actual, nfp.forecast, nfp.previous) == ("50K", "60K", "64K")
    row = nfp.row(nfp.natural_key, T2)
    assert (row["actual_value"], row["forecast_value"], row["previous_value"]) == (50e3, 60e3, 64e3)
    jolts = by_title(week.events, "JOLTS Job Openings").row("k", T1)
    assert (jolts["forecast_value"], jolts["previous_value"]) == (7_600_000, 7_670_000)
    adp = by_title(week.events, "ADP Non-Farm Employment Change").row("k", T1)
    assert adp["previous_value"] == -32_000

    holiday = by_title(week.events, "Bank Holiday")
    assert (holiday.impact, holiday.currency) == ("holiday", "JPY")
    assert holiday.scheduled_at == utc(2026, 1, 5, 5)
    tentative = by_title(week.events, "FOMC Member Barkin Speaks")
    assert tentative.scheduled_at is None and tentative.time_label == "Tentative"
    assert tentative.scheduled_date == date(2026, 1, 6)
    assert by_title(week.events, "IMF Meetings").currency == "ALL"
    minutes = by_title(week.events, "FOMC Meeting Minutes")  # the unknown "url" is ignored
    assert minutes.scheduled_at == utc(2026, 1, 7, 19) and minutes.forecast is None


def test_normalise_summer_week() -> None:
    week = forexfactory.parse(SUMMER)
    assert not week.skipped
    assert by_title(week.events, "CPI m/m").scheduled_at == utc(2026, 7, 14, 12, 30)  # EDT
    assert by_title(week.events, "Federal Funds Rate").scheduled_at == utc(2026, 7, 15, 18)
    day = by_title(week.events, "Independence Day")  # a bare day: All Day
    assert day.scheduled_at is None and day.time_label == "All Day"
    assert day.scheduled_date == date(2026, 7, 13)


def test_parse_checks_the_shape() -> None:
    with pytest.raises(forexfactory.FetchError, match="not a list"):
        forexfactory.parse(b'{"error": "rate limited"}')
    with pytest.raises(forexfactory.FetchError, match="not JSON"):
        forexfactory.parse(b"<html>blocked</html>")
    week = forexfactory.parse(
        b'[1, {"title": "X", "country": "USD", "date": "2026-01-05T10:00:00-05:00",'
        b' "impact": "Extreme"}, {"title": "", "country": "USD", "date": "2026-01-05",'
        b' "impact": "Low"}, {"title": "Ok", "country": "usd", "date": "2026-01-05T10:00:00'
        b'-05:00", "impact": "LOW", "forecast": null}]'
    )
    assert [e.title for e in week.events] == ["Ok"] and week.events[0].currency == "USD"
    assert [s.split(":")[0] for s in week.skipped] == ["item 0", "item 1", "item 2"]
    assert "unknown impact" in week.skipped[1] and "title" in week.skipped[2]


# --- versions -----------------------------------------------------------------------------------


async def test_same_payload_twice_inserts_once(session: AsyncSession) -> None:
    events = forexfactory.parse(WINTER).events
    assert await service.upsert_versions(session, events, T1) == {"inserted": 16, "unchanged": 0}
    later = T1 + timedelta(hours=4)
    assert await service.upsert_versions(session, events, later) == {
        "inserted": 0,
        "unchanged": 16,
    }
    rows = (await session.scalars(select(EconomicEvent))).all()
    assert len(rows) == 16 and {r.fetched_at for r in rows} == {T1}


async def test_actual_is_a_new_version_of_the_same_event(session: AsyncSession) -> None:
    before = usd("CPI m/m", utc(2026, 1, 13, 13, 30), forecast="0.3%", previous="0.2%")
    after = replace(before, actual="0.4%")
    await service.upsert_versions(session, [before], T1)
    assert await service.upsert_versions(session, [after], T2) == {"inserted": 1, "unchanged": 0}
    versions = await service.history(session, before.natural_key)
    assert [v.actual for v in versions] == [None, "0.4%"]
    assert [v.fetched_at for v in versions] == [T1, T2]
    assert versions[1].actual_value == 0.4 and len({v.event_key for v in versions}) == 1


async def test_moved_time_in_the_same_week_is_the_same_event(session: AsyncSession) -> None:
    wednesday = usd("Fed Chair Powell Testifies", utc(2026, 1, 7, 15))
    claims = usd("Unemployment Claims", utc(2026, 1, 8, 13, 30), impact="medium")
    await service.upsert_versions(session, [wednesday, claims], T1)
    # the next fetch shows it on Thursday (same week), and a brand-new event
    thursday = usd("Fed Chair Powell Testifies", utc(2026, 1, 8, 15))
    new = usd("Beige Book", utc(2026, 1, 7, 19), impact="medium")
    counts = await service.upsert_versions(session, [thursday, claims, new], T2)
    assert counts == {"inserted": 2, "unchanged": 1}

    key = wednesday.natural_key
    assert thursday.natural_key != key  # a new day would be a new natural key ...
    versions = await service.history(session, key)  # ... but it is matched to the event
    assert [v.scheduled_at for v in versions] == [utc(2026, 1, 7, 15), utc(2026, 1, 8, 15)]
    assert await service.history(session, thursday.natural_key) == []
    assert len(await service.history(session, new.natural_key)) == 1  # a new event: new key

    # the next week's event of the same title is another event
    next_week = usd("Fed Chair Powell Testifies", utc(2026, 1, 13, 15))
    await service.upsert_versions(session, [next_week], T2 + timedelta(days=4))
    assert len(await service.history(session, next_week.natural_key)) == 1
    assert len(await service.history(session, key)) == 2


async def test_present_events_are_not_taken_as_moved(session: AsyncSession) -> None:
    """Two speeches of the same title in one week, both still in the feed: two events."""
    monday = usd("FOMC Member Speaks", utc(2026, 1, 5, 15), impact="medium")
    await service.upsert_versions(session, [monday], T1)
    wednesday = usd("FOMC Member Speaks", utc(2026, 1, 7, 15), impact="medium")
    await service.upsert_versions(session, [monday, wednesday], T2)
    assert len(await service.history(session, monday.natural_key)) == 1
    assert len(await service.history(session, wednesday.natural_key)) == 1


# --- point in time ------------------------------------------------------------------------------


async def _two_versions(session: AsyncSession) -> EventIn:
    nfp = usd("Non-Farm Employment Change", utc(2026, 1, 9, 13, 30), forecast="60K")
    await service.upsert_versions(session, [nfp], T1)
    await service.upsert_versions(session, [replace(nfp, actual="50K")], T2)
    return nfp


async def test_latest_as_of(session: AsyncSession) -> None:
    await _two_versions(session)
    start, end = utc(2026, 1, 9), utc(2026, 1, 10)

    async def known(as_of: datetime) -> list[EconomicEvent]:
        return await service.latest_as_of(session, start, end, as_of=as_of)

    [early] = await known(T1 + timedelta(hours=1))
    assert (early.forecast, early.actual, early.fetched_at) == ("60K", None, T1)
    [late] = await known(T2 + timedelta(hours=1))
    assert (late.actual, late.actual_value, late.fetched_at) == ("50K", 50_000, T2)
    assert await known(T1 - timedelta(seconds=1)) == []
    [now] = await service.latest_as_of(session, start, end)  # default: now
    assert now.actual == "50K"


async def test_filters_apply_to_the_latest_version(session: AsyncSession) -> None:
    """A version that moved out of the range (or lost impact) is not shown by its old one."""
    speech = usd("Fed Chair Powell Speaks", utc(2026, 1, 6, 15))
    await service.upsert_versions(session, [speech], T1)
    moved = usd("Fed Chair Powell Speaks", utc(2026, 1, 8, 15), impact="medium")
    await service.upsert_versions(session, [moved], T2)
    tuesday = (utc(2026, 1, 6), utc(2026, 1, 7))
    assert [e.title for e in await service.latest_as_of(session, *tuesday, as_of=T1)] == [
        "Fed Chair Powell Speaks"
    ]
    assert await service.latest_as_of(session, *tuesday) == []
    thursday = (utc(2026, 1, 8), utc(2026, 1, 9))
    assert await service.latest_as_of(session, *thursday, min_impact="high") == []
    [found] = await service.latest_as_of(session, *thursday, min_impact="medium")
    assert found.scheduled_at == utc(2026, 1, 8, 15)


# --- for_evaluate (B9) --------------------------------------------------------------------------


async def test_for_evaluate(session: AsyncSession, db_connection) -> None:
    await service.upsert_versions(session, forexfactory.parse(WINTER).events, T1)
    bar = utc(2026, 1, 9, 13, 15)
    statements: list[str] = []
    sync = db_connection.sync_connection

    def count(*args) -> None:
        statements.append(args[2])

    sa_event.listen(sync, "before_cursor_execute", count)
    try:
        started = time.perf_counter()
        items = await service.for_evaluate(session, bar)
        elapsed = time.perf_counter() - started
    finally:
        sa_event.remove(sync, "before_cursor_execute", count)
    assert len([s for s in statements if s.startswith("SELECT")]) == 1
    print(f"for_evaluate: 1 query, {elapsed * 1000:.1f} ms")
    # USD, medium or high, with a time, between 07:15 and 19:15 UTC: not the EUR CPI, the low
    # "IMF Meetings" (ALL) or Thursday's events
    assert items == [
        {"ts": "2026-01-09T13:30:00Z", "currency": "USD", "impact": "high",
         "title": "Average Hourly Earnings m/m"},
        {"ts": "2026-01-09T13:30:00Z", "currency": "USD", "impact": "high",
         "title": "Non-Farm Employment Change"},
        {"ts": "2026-01-09T13:30:00Z", "currency": "USD", "impact": "high",
         "title": "Unemployment Rate"},
        {"ts": "2026-01-09T15:00:00Z", "currency": "USD", "impact": "medium",
         "title": "Prelim UoM Consumer Sentiment"},
    ]  # fmt: skip
    # the window is ±6 h: Wednesday 14:00 EST (19:00 UTC) is seen from 13:00 to 01:00
    titles = [i["title"] for i in await service.for_evaluate(session, utc(2026, 1, 8, 1))]
    assert titles == ["FOMC Meeting Minutes"]
    assert await service.for_evaluate(session, utc(2026, 1, 8, 1, 1)) == []
    # Tentative (no time) is never sent; a backtest asks as of the bar: nothing known yet
    assert await service.for_evaluate(session, utc(2026, 1, 6, 5)) == []
    assert await service.for_evaluate(session, bar, as_of=T1 - timedelta(minutes=1)) == []
    euro = await service.for_evaluate(session, utc(2026, 1, 7, 10), currencies=["EUR"])
    assert euro == [
        {"ts": "2026-01-07T10:00:00Z", "currency": "EUR", "impact": "high",
         "title": "CPI Flash Estimate y/y"}
    ]  # fmt: skip


# --- read API -----------------------------------------------------------------------------------


async def test_events_endpoint(client: AsyncClient, session: AsyncSession, trader_headers) -> None:
    await service.upsert_versions(session, forexfactory.parse(WINTER).events, T1)
    params = {"start": "2026-01-05T00:00:00Z", "end": "2026-01-10T00:00:00Z"}
    res = await client.get("/api/v1/calendar/events", params=params, headers=trader_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["currencies"] == ["USD"] and body["min_impact"] == "low"
    titles = [e["title"] for e in body["events"]]
    assert titles[:3] == [
        "ISM Manufacturing PMI",
        "FOMC Member Barkin Speaks",  # Tentative: sorted at the start of its New York day
        "ADP Non-Farm Employment Change",
    ]
    assert len(titles) == 11 and "Bank Holiday" not in titles  # JPY
    first = body["events"][0]
    assert set(first) == {
        "event_key", "scheduled_at", "scheduled_date", "time_label", "currency", "impact",
        "title", "actual", "forecast", "previous", "actual_value", "forecast_value",
        "previous_value", "fetched_at", "source",
    }  # fmt: skip
    assert first["scheduled_at"] == "2026-01-05T15:00:00Z" and first["forecast_value"] == 48.3

    res = await client.get(
        "/api/v1/calendar/events",
        params={**params, "currencies": "ALL", "min_impact": "holiday"},
        headers=trader_headers,
    )
    assert len(res.json()["events"]) == 16 and res.json()["currencies"] is None
    res = await client.get(
        "/api/v1/calendar/events",
        params={**params, "currencies": "eur,gbp", "min_impact": "high"},
        headers=trader_headers,
    )
    assert [e["title"] for e in res.json()["events"]] == ["CPI Flash Estimate y/y"]

    too_long = {"start": "2026-01-01T00:00:00Z", "end": "2026-02-02T00:00:00Z"}
    res = await client.get("/api/v1/calendar/events", params=too_long, headers=trader_headers)
    assert res.status_code == 422
    assert (await client.get("/api/v1/calendar/events", params=params)).status_code == 401


async def test_as_of_is_for_admins_only(
    client: AsyncClient, session: AsyncSession, make_user, login, trader_headers
) -> None:
    nfp = await _two_versions(session)
    await make_user("cal-admin@example.com", role=UserRole.admin)
    admin = {"Authorization": f"Bearer {(await login('cal-admin@example.com'))['access_token']}"}
    params = {
        "start": "2026-01-09T00:00:00Z",
        "end": "2026-01-10T00:00:00Z",
        "as_of": (T1 + timedelta(hours=1)).isoformat(),
    }
    res = await client.get("/api/v1/calendar/events", params=params, headers=admin)
    [event] = res.json()["events"]
    assert event["actual"] is None and event["forecast"] == "60K"
    assert res.json()["as_of"] == "2026-01-04T19:00:00Z"

    res = await client.get("/api/v1/calendar/events", params=params, headers=trader_headers)
    [event] = res.json()["events"]  # as_of ignored: what is known now
    assert event["actual"] == "50K"
    assert res.json()["as_of"] != "2026-01-04T19:00:00Z"

    res = await client.get(
        f"/api/v1/calendar/events/{nfp.natural_key}/history", headers=trader_headers
    )
    assert res.status_code == 200
    assert [v["actual"] for v in res.json()["versions"]] == [None, "50K"]
    missing = await client.get(
        f"/api/v1/calendar/events/{'0' * 64}/history", headers=trader_headers
    )
    assert missing.status_code == 404
