"""B6 calendar history: the CSV loader (script and shared import) on a small hand-made fixture
(never the Kaggle data), the history fetched_at approximation, the admin import endpoint."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import calendar as calendar_api
from app.calendar import csv_import, service
from app.calendar.csv_import import CsvFormatError, ImportOptions, import_rows, reader
from app.calendar.events import EventIn
from app.models.economic_event import EconomicEvent
from scripts import load_calendar_csv

CSV = Path(__file__).parent / "fixtures" / "calendar_history.csv"
NY = "America/New_York"
SKIPPED = {
    "bad date": 1,
    "bad impact": 1,
    "before --from": 2,
    "malformed row": 1,
    "missing title": 1,
}
IMPACTS = {"high": 17, "holiday": 2, "low": 2, "medium": 3}


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


async def _import(session: AsyncSession | None, **options) -> dict:
    with CSV.open(encoding="utf-8-sig", newline="") as handle:
        summary = await import_rows(session, reader(handle), ImportOptions(tz=NY, **options))
    return summary.as_dict()


def test_script_dry_run(capsys) -> None:
    assert load_calendar_csv.main(["--file", str(CSV), "--tz", NY, "--dry-run"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == (
        "columns: date=Date, time=Time, currency=Currency, impact=Impact, title=Event, "
        "actual=Actual, forecast=Forecast, previous=Previous"
    )
    assert out[1] == "parsed rows (first 5):"
    assert out[2].split() == ["2018-01-01", "(All", "Day)", "USD", "holiday", "Bank", "Holiday"]
    assert out[4].split()[:3] == ["2018-01-04T13:15:00+00:00", "USD", "high"]  # 8:15am EST
    assert out[4].endswith("actual=250K forecast=190K previous=185K")
    assert "rows read: 30" in out
    assert "date range: 2018-01-01 to 2024-12-20" in out
    assert "versions: 40" in out and out[-1] == "dry run: nothing written"
    assert any(line.startswith("skipped: ") and '"before --from": 2' in line for line in out)


def test_script_needs_a_timezone(capsys) -> None:
    assert load_calendar_csv.main(["--file", str(CSV), "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "no timezone information" in err and "never guessed" in err
    assert load_calendar_csv.main(["--file", str(CSV), "--tz", "Mars/Olympus"]) == 2
    assert "unknown timezone" in capsys.readouterr().err
    assert load_calendar_csv.main(["--file", "missing.csv", "--tz", NY]) == 2


async def test_import_counts_and_idempotence(session: AsyncSession) -> None:
    dry = await _import(None, dry_run=True)
    assert (dry["versions"], dry["inserted"]) == (40, 0)

    first = await _import(session)
    assert first["rows_read"] == 30 and first["skipped"] == SKIPPED
    assert first["skipped_examples"] == [
        "line 22: malformed row",
        "line 23: bad impact",
        "line 24: bad date",
        "line 25: missing title",
    ]
    assert first["events_per_impact"] == IMPACTS
    assert (first["first_date"], first["last_date"]) == ("2018-01-01", "2024-12-20")
    # 24 events: 16 with an actual (two versions each) and 8 without
    assert (first["versions"], first["inserted"], first["unchanged"]) == (40, 40, 0)
    assert await session.scalar(select(func.count()).select_from(EconomicEvent)) == 40

    second = await _import(session)
    assert (second["inserted"], second["unchanged"]) == (0, 40)
    since = await _import(session, since=date(2024, 1, 1))
    assert since["skipped"]["before --from"] == 20 and since["inserted"] == 0


async def test_history_versions_are_point_in_time(session: AsyncSession) -> None:
    await _import(session)
    nfp_at = utc(2018, 1, 5, 13, 30)  # 8:30am EST
    window = (nfp_at - timedelta(hours=1), nfp_at + timedelta(hours=1))
    nfp = lambda rows: [r for r in rows if r.title == "Non-Farm Employment Change"]  # noqa: E731

    [before] = nfp(await service.latest_as_of(session, *window, as_of=nfp_at - timedelta(hours=1)))
    assert (before.actual, before.forecast, before.previous) == (None, "191K", "252K")
    assert before.fetched_at == nfp_at - timedelta(days=7)
    assert before.source == "forexfactory_kaggle"
    [after] = nfp(await service.latest_as_of(session, *window, as_of=nfp_at))
    assert (after.actual, after.actual_value, after.fetched_at) == ("148K", 148_000, nfp_at)
    assert after.event_key == before.event_key
    assert nfp(await service.latest_as_of(session, *window, as_of=utc(2017, 12, 28))) == []

    # a summer row: EDT
    [cpi] = await service.latest_as_of(
        session, utc(2024, 7, 11), utc(2024, 7, 12), min_impact="high"
    )
    assert cpi.scheduled_at == utc(2024, 7, 11, 12, 30) and cpi.actual_value == -0.1
    # All Day and Tentative: no time, kept by their day
    holidays = await service.latest_as_of(
        session, utc(2018, 1, 1), utc(2018, 1, 2), min_impact="holiday"
    )
    assert [(h.title, h.scheduled_at, h.time_label) for h in holidays] == [
        ("Bank Holiday", None, "All Day")
    ]
    [speech] = await service.latest_as_of(session, utc(2018, 3, 21), utc(2018, 3, 22))
    assert speech.time_label == "Tentative" and speech.scheduled_at is None
    # "<1.50%" is kept as published, without a number
    fomc = await service.latest_as_of(session, utc(2018, 1, 31, 19), utc(2018, 1, 31, 19))
    rate = {e.title: e for e in fomc}["Federal Funds Rate"]
    assert (rate.actual, rate.actual_value, rate.previous) == ("<1.50%", None, "<1.50%")


async def test_history_and_live_merge(session: AsyncSession) -> None:
    """The same event seen live has the same event_key; the same values insert nothing."""
    await _import(session)
    live = EventIn.build(
        source="forexfactory_live",
        currency="USD",
        title="Core PCE Price Index m/m",
        impact="high",
        scheduled_at=utc(2024, 12, 20, 13, 30),
        forecast="0.2%",
        previous="0.3%",
    )
    assert await service.upsert_versions(session, [live], utc(2024, 12, 16)) == {
        "inserted": 0,
        "unchanged": 1,
    }
    released = replace(live, actual="0.1%")
    await service.upsert_versions(session, [released], utc(2024, 12, 20, 13, 31))
    versions = await service.history(session, live.natural_key)
    assert [(v.source, v.actual) for v in versions] == [
        ("forexfactory_kaggle", None),
        ("forexfactory_live", "0.1%"),
    ]


def test_column_mapping() -> None:
    columns = csv_import.detect_columns(
        ["Start", "Name", "Impact", "Currency", "Actual"], {"title": "Name"}
    )
    assert columns == {"date": 0, "title": 1, "impact": 2, "currency": 3, "actual": 4}
    with pytest.raises(CsvFormatError, match="no column for title"):
        csv_import.detect_columns(["Date", "Currency", "Impact"], {})
    with pytest.raises(CsvFormatError, match="'Nope'"):
        csv_import.detect_columns(["Date", "Currency", "Impact", "Event"], {"title": "Nope"})
    assert csv_import.parse_mapping("title=Name, date=Start") == {"title": "Name", "date": "Start"}
    with pytest.raises(CsvFormatError):
        csv_import.parse_mapping("title")
    with pytest.raises(CsvFormatError, match="unknown field"):
        ImportOptions(tz="UTC", mapping={"country": "Cur"})


def test_offsets_in_the_file_need_no_tz() -> None:
    columns = csv_import.detect_columns(["DateTime", "Currency", "Impact", "Event"], {})
    event = csv_import.parse_row(
        ["2024-07-11T08:30:00-04:00", "usd", "High", "CPI m/m"], columns, ImportOptions(tz=None)
    )
    assert event.scheduled_at == utc(2024, 7, 11, 12, 30) and event.currency == "USD"
    with pytest.raises(CsvFormatError, match="no timezone"):
        csv_import.parse_row(
            ["2024-07-11 08:30:00", "USD", "High", "CPI m/m"], columns, ImportOptions(tz=None)
        )
    utc_row = csv_import.parse_row(
        ["2024-07-11 12:30:00", "USD", "red", "CPI m/m"], columns, ImportOptions(tz="UTC")
    )
    assert utc_row.scheduled_at == utc(2024, 7, 11, 12, 30) and utc_row.impact == "high"


# --- admin import endpoint ----------------------------------------------------------------------


def _upload(content: bytes | None = None) -> dict:
    return {"file": ("calendar_history.csv", content or CSV.read_bytes(), "text/csv")}


async def test_admin_import(
    client: AsyncClient, session: AsyncSession, admin_headers, trader_headers
) -> None:
    url = "/api/v1/admin/calendar/import"
    res = await client.post(url, params={"tz": NY}, files=_upload(), headers=trader_headers)
    assert res.status_code == 403

    res = await client.post(
        url, params={"tz": NY, "dry_run": "true"}, files=_upload(), headers=admin_headers
    )
    assert res.status_code == 200, res.text
    assert (res.json()["versions"], res.json()["inserted"]) == (40, 0)
    assert len(res.json()["sample"]) == 5

    res = await client.post(url, params={"tz": NY}, files=_upload(), headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    script = await _import(None, dry_run=True)  # the same counts as the script
    for key in ("rows_read", "skipped", "versions", "events_per_impact", "first_date"):
        assert body[key] == script[key]
    assert (body["inserted"], body["unchanged"], body["dry_run"]) == (40, 0, False)
    assert await session.scalar(select(func.count()).select_from(EconomicEvent)) == 40
    again = await client.post(url, params={"tz": NY}, files=_upload(), headers=admin_headers)
    assert (again.json()["inserted"], again.json()["unchanged"]) == (0, 40)


async def test_admin_import_errors(
    client: AsyncClient, admin_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "/api/v1/admin/calendar/import"
    res = await client.post(url, files=_upload(), headers=admin_headers)  # no tz
    assert res.status_code == 422 and "no timezone information" in res.json()["detail"]
    res = await client.post(
        url, params={"tz": "Nowhere/City"}, files=_upload(), headers=admin_headers
    )
    assert res.status_code == 422 and "unknown timezone" in res.json()["detail"]
    res = await client.post(
        url, params={"tz": NY, "map": "title=Nope"}, files=_upload(), headers=admin_headers
    )
    assert res.status_code == 422 and "'Nope'" in res.json()["detail"]
    res = await client.post(url, params={"tz": NY}, data={"x": "1"}, headers=admin_headers)
    assert res.status_code == 422 and "multipart field 'file'" in res.json()["detail"]

    # the size cap: on the declared length, and on the uploaded file itself
    monkeypatch.setattr(calendar_api, "MAX_IMPORT_BYTES", 1000)
    res = await client.post(url, params={"tz": NY}, files=_upload(), headers=admin_headers)
    assert res.status_code == 413 and res.json()["detail"] == "the CSV is larger than 1,000 bytes"
    monkeypatch.setattr(calendar_api, "MULTIPART_SLACK", 0)
    res = await client.post(url, params={"tz": NY}, files=_upload(), headers=admin_headers)
    assert res.status_code == 413
