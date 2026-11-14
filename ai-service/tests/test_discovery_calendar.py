"""The calendar importer (app/discovery/calendar.py)."""

from app.discovery import calendar as cal

ROWS = (
    "time_server,time_utc,currency,country,event,importance,impact,actual,forecast,previous,"
    "revised,event_id,value_id\r\n"
    "2024.07.05 14:30:00,2024.07.05 12:30:00,USD,United States,Nonfarm Payrolls,3,1,206.0,190.0,"
    "218.0,,840030016,1\r\n"
    "2024.01.05 15:30:00,2024.01.05 13:30:00,EUR,Euro Area,Caf\x96 index,1,0,,,,,1,2\r\n"
)


def test_read_uses_the_utc_column_and_cp1252(tmp_path) -> None:
    f = tmp_path / "c.csv"
    f.write_bytes(ROWS.encode("latin-1"))
    c = cal.read(f)
    nfp = c[c["event"] == "Nonfarm Payrolls"].iloc[0]
    assert nfp["ts_utc"].tz_convert(cal.NY).strftime("%H:%M") == "08:30"  # summer, EDT
    assert nfp["surprise"] == 16.0
    assert c["ts_utc"].is_monotonic_increasing
    assert c.iloc[0]["event"].startswith("Caf")
