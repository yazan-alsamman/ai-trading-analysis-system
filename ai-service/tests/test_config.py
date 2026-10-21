from datetime import date

from app import cli, config


def test_the_six_instruments_in_scope() -> None:
    assert set(config.instruments()) == {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"}
    xau = config.instruments()["XAUUSD"]
    assert (xau.point, xau.contract_size, xau.daily_break) == (0.01, 100, ("17:00", "18:00"))
    assert config.instruments()["USDJPY"].quote_currency == "JPY"


def test_splits_follow_d23() -> None:
    s = config.splits()
    assert s.server_tz == "Europe/Athens"
    assert s.development == (date(2012, 1, 1), date(2018, 1, 1))
    assert s.walk_forward == (date(2018, 1, 1), date(2024, 7, 1))
    assert s.walk_forward_test_months == 6
    assert s.secondary_holdout == (date(2024, 7, 1), date(2026, 1, 10))
    assert s.lockbox_start == date(2026, 1, 10)
    assert s.embargo_days == 1


def test_cli_runs_a_command_and_rejects_unknown_ones(capsys) -> None:
    assert cli.main(["config"]) == 0
    assert '"lockbox_start": "2026-01-10"' in capsys.readouterr().out
    assert cli.main(["nope"]) == 2
    assert cli.main([]) == 2
