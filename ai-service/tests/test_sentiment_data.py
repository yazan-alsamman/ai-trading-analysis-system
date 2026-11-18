"""Gold-news sentiment data and gates (``app/research/sentiment``) on hand-built inputs."""

from __future__ import annotations

import hashlib
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.research.sentiment import data as sd
from app.research.sentiment import gates as sg

# ------------------------------------------------------------------------------------- helpers


def headlines(rows: list[tuple[str, str]]) -> pd.DataFrame:
    """(ISO date, headline) in file order -> the columns ``dedupe`` needs."""
    return pd.DataFrame({
        "row_id": np.arange(len(rows), dtype=np.int64),
        "date": pd.to_datetime([d for d, _ in rows]),
        "headline": [h for _, h in rows],
        "price_sentiment": "positive",
    })  # fmt: skip


def bars(rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", *sd.PRICE_COLUMNS]).assign(
        date=lambda d: pd.to_datetime(d["date"])
    )


CONFIG_TEXT = """
[paths]
root = "data/sentiment"
raw = "data/sentiment/raw"
processed = "data/sentiment/processed"
report = "docs/gates.md"

[files.a]
path = "raw/a.txt"
sha256 = "{sha}"

[files.b]
path = "raw/b.txt"
sha256 = ""
optional = true

[dedupe]
near_jaccard = 0.8
window_days = 3

[split]
min_test = 2
default = {{ train_last = "2012-12-31", val_last = "2015-12-31" }}
fallback = {{ train_last = "2011-12-31", val_last = "2014-12-31" }}

[prices]
first_date = "2003-01-01"
stop_before = "{stop}"

[gates]
g2_min_close_corr = 0.99
g2_return_diff = 0.005
g2_list = 20

# written by gates
[class_weights]
negative = 0.0
neutral = 0.0
positive = 0.0
"""


def make_config(tmp_path: Path, content: bytes = b"abc", sha: str | None = None,
                stop: str = "2026-01-10") -> sd.Config:  # fmt: skip
    raw = tmp_path / "data" / "sentiment" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.txt").write_bytes(content)
    sha = hashlib.sha256(content).hexdigest() if sha is None else sha
    path = tmp_path / "sentiment.toml"
    path.write_text(CONFIG_TEXT.format(sha=sha, stop=stop), encoding="utf-8")
    return sd.load_config(path, base=tmp_path)


# ----------------------------------------------------------------------------- config / SHA-256


def test_verify_files_accepts_matching_sha_and_missing_optional(tmp_path):
    cfg = make_config(tmp_path)
    assert sd.verify_files(cfg) == {"a": "ok", "b": "missing"}


def test_sha256_mismatch_stops_the_run(tmp_path):
    cfg = make_config(tmp_path, sha="0" * 64)
    with pytest.raises(sd.ChecksumError, match="SHA-256"):
        sd.verify_files(cfg)


def test_missing_required_file_stops_the_run(tmp_path):
    cfg = make_config(tmp_path)
    cfg.files["a"].path.unlink()
    with pytest.raises(sd.ChecksumError, match="not found"):
        sd.verify_files(cfg)


def test_optional_file_present_without_recorded_sha_stops_the_run(tmp_path):
    cfg = make_config(tmp_path)
    cfg.files["b"].path.write_bytes(b"x")
    with pytest.raises(sd.ChecksumError, match="no SHA-256"):
        sd.verify_files(cfg)


def test_cli_returns_1_on_sha_mismatch(tmp_path, monkeypatch, capsys):
    from app.research.sentiment import cli

    cfg = make_config(tmp_path, sha="f" * 64)
    monkeypatch.setattr(sd, "load_config", lambda: cfg)
    assert cli.main(["data"]) == 1
    assert "stopped" in capsys.readouterr().err


def test_price_stop_after_lockbox_is_refused(tmp_path):
    with pytest.raises(ValueError, match="lockbox"):
        make_config(tmp_path, stop="2026-01-11")


def test_write_class_weights_rewrites_only_the_last_table(tmp_path):
    cfg = make_config(tmp_path)
    sd.write_class_weights(cfg.path, {"positive": 0.5, "negative": 1.25, "neutral": 2.0})
    text = cfg.path.read_text(encoding="utf-8")
    assert text.endswith("[class_weights]\nnegative = 1.250000\nneutral = 2.000000\n"
                         "positive = 0.500000\n")  # fmt: skip
    assert sd.load_config(cfg.path, base=tmp_path).class_weights["neutral"] == 2.0
    assert "near_jaccard = 0.8" in text


# --------------------------------------------------------------------------------- loaders


def test_load_gold_maps_columns_labels_and_reports_bad_dates(tmp_path):
    header = ",".join(sd.GOLD_COLUMNS)
    lines = [
        header,
        '28-01-2016,http://x/2016-01-28/a,"gold up, $5",1,0,0,0,1,0,positive',
        "0201-04-27,http://x/2015-04-27/b,gold flat,0,1,0,0,1,0,none",
        "13-09-2017,http://x/c,gold down,0,0,1,1,0,1,Negative",
    ]
    path = tmp_path / "gold.csv"
    path.write_bytes(("﻿" + "\n".join(lines) + "\n").encode("utf-8"))
    rows, bad = sd.load_gold(path)
    assert rows["row_id"].tolist() == [0, 2]
    assert rows["date"].tolist() == [pd.Timestamp("2016-01-28"), pd.Timestamp("2017-09-13")]
    assert rows["label"].tolist() == ["positive", "negative"]
    assert rows["url_date"].iloc[0] == pd.Timestamp("2016-01-28")
    assert pd.isna(rows["url_date"].iloc[1])
    assert rows["future_info"].tolist() == [0, 1]
    assert bad["row_id"].tolist() == [1]
    assert bad["shape"].tolist() == ["9999-99-99"]
    assert bad["url_date"].iloc[0] == pd.Timestamp("2015-04-27")


def test_none_maps_to_neutral_with_flag(tmp_path):
    header = ",".join(sd.GOLD_COLUMNS)
    path = tmp_path / "gold.csv"
    path.write_text(header + "\n01-02-2010,u,h,0,0,0,0,1,0,none\n", encoding="utf-8")
    rows, _ = sd.load_gold(path)
    assert rows["label"].iloc[0] == "neutral" and bool(rows["is_none"].iloc[0])


def test_load_gold_rejects_unknown_sentiment(tmp_path):
    header = ",".join(sd.GOLD_COLUMNS)
    path = tmp_path / "gold.csv"
    path.write_text(header + "\n01-02-2010,u,h,0,0,0,0,1,0,bullish\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Price Sentiment"):
        sd.load_gold(path)


def test_load_fpb_splits_on_the_last_at_sign(tmp_path):
    path = tmp_path / "fpb.txt"
    path.write_bytes("Sales rose 5 % @ 2009@positive\r\nCaf\xe9 flat@neutral\r\n\r\n".encode(
        "latin-1"))  # fmt: skip
    df = sd.load_fpb(path)
    assert df.to_dict("list") == {
        "sentence": ["Sales rose 5 % @ 2009", "Caf\xe9 flat"],
        "label": ["positive", "neutral"],
    }


def test_load_fpb_rejects_a_bad_label(tmp_path):
    path = tmp_path / "fpb.txt"
    path.write_text("x@bullish\n", encoding="latin-1")
    with pytest.raises(ValueError, match="line 1"):
        sd.load_fpb(path)


# ---------------------------------------------------------------------------------- G1 dedupe


def test_normalise_strips_punctuation_digits_and_case():
    assert sd.normalise("  Gold's UP $1,116.10/oz!!  in   Asia ") == "gold s up oz in asia"
    assert sd.normalise("2016") == ""
    assert sd.normalise("Comex\tgold\nsettles") == "comex gold settles"


def test_jaccard():
    assert sd.jaccard(frozenset("ab"), frozenset("ab")) == 1.0
    assert sd.jaccard(frozenset("abcd"), frozenset("abce")) == pytest.approx(3 / 5)
    assert sd.jaccard(frozenset(), frozenset()) == 0.0


def test_exact_duplicate_keeps_the_earliest_date_not_the_first_row():
    df = headlines([
        ("2016-03-10", "Gold rises $5 to $1,250"),
        ("2016-03-01", "gold rises 7 to 1,240."),
        ("2016-03-02", "silver falls"),
    ])  # fmt: skip
    out = sd.dedupe(df, 0.8, 3).set_index("row_id")
    assert out.loc[1, "keep"] and not out.loc[0, "keep"]
    assert out.loc[0, "dup_exact"] and out.loc[0, "dup_of"] == 1
    assert out.loc[2, "keep"] and out.loc[2, "dup_of"] == -1


def test_exact_duplicate_on_the_same_day_keeps_file_order():
    df = headlines([("2016-03-01", "Gold up"), ("2016-03-01", "gold up!")])
    out = sd.dedupe(df, 0.8, 3).set_index("row_id")
    assert out.loc[0, "keep"] and out.loc[1, "dup_exact"]


NEAR_A = "gold futures settle higher on weak dollar data"  # 8 tokens
NEAR_B = "gold futures settle higher on weak dollar data today"  # 9 tokens, Jaccard 8/9


@pytest.mark.parametrize(
    ("later", "dropped"),
    [("2016-03-01", True), ("2016-03-04", True), ("2016-03-05", False)],
)
def test_near_duplicate_window_edge(later, dropped):
    # the window is +-3 days inclusive: 0 and 3 days apart are compared, 4 days apart are not
    df = headlines([("2016-03-01", NEAR_A), (later, NEAR_B)])
    out = sd.dedupe(df, 0.8, 3).set_index("row_id")
    assert out.loc[0, "keep"]
    assert bool(out.loc[1, "dup_near"]) is dropped
    if dropped:
        assert out.loc[1, "dup_of"] == 0 and out.loc[1, "dup_jaccard"] == pytest.approx(8 / 9)


def test_near_duplicate_earlier_by_date_is_kept_even_if_later_in_file():
    df = headlines([("2016-03-03", NEAR_A), ("2016-03-01", NEAR_B)])
    out = sd.dedupe(df, 0.8, 3).set_index("row_id")
    assert out.loc[1, "keep"] and out.loc[0, "dup_near"]


def test_near_duplicate_below_threshold_is_kept():
    # 5 shared of 11 distinct tokens: 0.45 < 0.8
    df = headlines(
        [("2016-03-01", NEAR_A), ("2016-03-02", "gold futures settle lower on strong euro data")]
    )
    out = sd.dedupe(df, 0.8, 3)  # fmt: skip
    assert out["keep"].all()


def test_near_duplicates_compare_with_kept_headlines_only():
    a = "a b c d e f g h i j"
    b = "a b c d e f g h i k"  # Jaccard(a, b) = 9/11 = 0.82
    c = "a b c d e f g h l k"  # Jaccard(b, c) = 0.82, Jaccard(a, c) = 8/12 = 0.67
    df = headlines([("2016-03-01", a), ("2016-03-02", b), ("2016-03-03", c)])
    out = sd.dedupe(df, 0.8, 3).set_index("row_id")
    assert out["keep"].tolist() == [True, False, True]


# -------------------------------------------------------------------------------------- split


def test_assign_split_boundaries_are_inclusive():
    d = pd.Series(pd.to_datetime(["2012-12-31", "2013-01-01", "2015-12-31", "2016-01-01"]))
    got = sd.assign_split(d, date(2012, 12, 31), date(2015, 12, 31)).tolist()
    assert got == ["train", "validation", "validation", "test"]


def test_split_default_when_test_is_large_enough():
    d = pd.Series(pd.to_datetime(["2010-05-01", "2014-05-01", "2015-06-01", "2016-02-01",
                                  "2017-02-01"]))  # fmt: skip
    c = sd.choose_split(d, (date(2012, 12, 31), date(2015, 12, 31)),
                        (date(2011, 12, 31), date(2014, 12, 31)), min_test=2)  # fmt: skip
    assert c.name == "default" and c.counts == {"train": 1, "validation": 2, "test": 2}


def test_split_falls_back_when_test_is_too_small():
    d = pd.Series(pd.to_datetime(["2010-05-01", "2012-05-01", "2014-05-01", "2015-06-01",
                                  "2016-02-01"]))  # fmt: skip
    c = sd.choose_split(d, (date(2012, 12, 31), date(2015, 12, 31)),
                        (date(2011, 12, 31), date(2014, 12, 31)), min_test=2)  # fmt: skip
    assert c.name == "fallback"
    assert c.test_count_default == 1
    assert (c.train_last, c.val_last) == (date(2011, 12, 31), date(2014, 12, 31))
    assert c.counts == {"train": 1, "validation": 2, "test": 2}


def test_no_text_in_two_splits_check():
    norm = pd.Series(["gold up", "gold down", "gold up"])
    with pytest.raises(AssertionError, match="1 normalised"):
        sd.assert_disjoint(norm, pd.Series(["train", "test", "validation"]))
    sd.assert_disjoint(norm, pd.Series(["train", "test", "train"]))


def test_dedupe_then_split_leaves_no_text_in_two_splits():
    df = headlines([("2012-12-30", "gold rallies 2%"), ("2016-01-04", "Gold rallies 3%"),
                    ("2015-12-31", NEAR_A), ("2016-01-02", NEAR_B)])  # fmt: skip
    out = sd.dedupe(df, 0.8, 3)
    kept = out.loc[out["keep"]]
    split = sd.assign_split(kept["date"], date(2012, 12, 31), date(2015, 12, 31))
    sd.assert_disjoint(kept["norm"], split)
    assert split.tolist() == ["train", "validation"]


# ------------------------------------------------------------------------------------- prices


def test_sunday_merges_into_monday():
    b = bars([
        ("2016-01-08", 10, 11, 9, 10.5, 1),  # Friday
        ("2016-01-10", 10.6, 12.0, 10.2, 10.8, 2),  # Sunday
        ("2016-01-11", 10.8, 11.5, 9.5, 11.0, 3),  # Monday
    ])  # fmt: skip
    out, stats = sd.merge_sundays(b)
    assert out["date"].dt.day_of_week.tolist() == [4, 0]
    mon = out.iloc[1]
    assert (mon["open"], mon["high"], mon["low"], mon["close"], mon["volume"]) == (
        10.6, 12.0, 9.5, 11.0, 5)  # fmt: skip
    assert bool(mon["merged_sunday"]) and not bool(out.iloc[0]["merged_sunday"])
    assert stats == {"sunday_bars": 1, "sunday_merged": 1, "sunday_dropped": 0,
                     "saturday_bars": 0}  # fmt: skip


def test_sunday_without_a_following_monday_is_dropped():
    b = bars([
        ("2016-01-10", 10, 11, 9, 10, 1),  # Sunday, next bar is Tuesday (Monday holiday)
        ("2016-01-12", 10, 12, 9, 11, 1),  # Tuesday
        ("2016-01-17", 11, 13, 10, 12, 1),  # Sunday, last bar
    ])  # fmt: skip
    out, stats = sd.merge_sundays(b)
    assert out["date"].tolist() == [pd.Timestamp("2016-01-12")]
    assert out.iloc[0]["open"] == 10 and out.iloc[0]["high"] == 12
    assert stats["sunday_merged"] == 0 and stats["sunday_dropped"] == 2


def test_ohlc_violations():
    b = bars([
        ("2016-01-04", 10, 11, 9, 10, 1),  # fine
        ("2016-01-05", 10, 9.5, 9, 9.2, 1),  # high below open
        ("2016-01-06", 10, 11, 10.5, 10.8, 1),  # low above open
        ("2016-01-07", 10, 11, 0, 10, 1),  # low <= 0
    ])  # fmt: skip
    assert sd.ohlc_violations(b)["date"].dt.day.tolist() == [5, 6, 7]


def test_garman_klass_on_a_hand_computed_bar():
    # O 100, H 110, L 95, C 105:
    # 0.5 ln(110/95)^2 = 0.5 * 0.14660347^2 = 0.01074629
    # (2 ln 2 - 1) ln(1.05)^2 = 0.38629436 * 0.04879016^2 = 0.00091957
    got = sd.garman_klass(100.0, 110.0, 95.0, 105.0)
    assert float(got) == pytest.approx(0.01074629 - 0.00091957, abs=2e-8)
    out = sd.add_gk(bars([("2016-01-04", 100, 110, 95, 105, 1)]))
    assert math.exp(out["log_gk"].iloc[0]) == pytest.approx(0.00982672, abs=2e-8)


def test_gk_zero_range_gives_nan_log():
    out = sd.add_gk(bars([("2016-01-04", 100, 100, 100, 100, 1)]))
    assert out["gk_var"].iloc[0] == 0.0 and np.isnan(out["log_gk"].iloc[0])


def ms(day: str) -> int:
    return int(pd.Timestamp(day, tz="UTC").value // 1_000_000)


def test_read_dukascopy_stops_before_the_stop_date_without_reading_on(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        f"{ms('2026-01-08')},1,2,0.5,1.5,10\n"
        f"{ms('2026-01-09')},1.5,2,1,1.8,11\n"
        f"{ms('2026-01-10')},not,a,number\n"  # first lockbox line: only the timestamp is read
        "garbage that would fail to parse\n",
        encoding="ascii",
    )
    df = sd.read_dukascopy(path, date(2026, 1, 10))
    assert df["date"].tolist() == [pd.Timestamp("2026-01-08"), pd.Timestamp("2026-01-09")]
    assert df["close"].tolist() == [1.5, 1.8]


def test_read_dukascopy_rejects_a_bar_not_at_midnight(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text(f"timestamp,open,high,low,close,volume\n{ms('2016-01-04') + 3_600_000},"
                    "1,2,0.5,1.5,1\n", encoding="ascii")  # fmt: skip
    with pytest.raises(ValueError, match="00:00 UTC"):
        sd.read_dukascopy(path, date(2026, 1, 10))


# ------------------------------------------------------------------------------- G3 alignment


def test_weekend_headline_moves_to_the_next_price_day():
    cal = pd.Series(pd.to_datetime(["2016-01-08", "2016-01-11", "2016-01-13"]))  # Fri, Mon, Wed
    d = pd.Series(pd.to_datetime(["2016-01-09", "2016-01-10", "2016-01-11", "2016-01-12",
                                  "2016-01-14"]))  # fmt: skip
    got = sd.align_trade_dates(d, cal)
    want = ["2016-01-11", "2016-01-11", "2016-01-11", "2016-01-13"]
    assert got[:4].tolist() == [pd.Timestamp(x) for x in want]
    assert pd.isna(got.iloc[4])


def test_g3_table_splits_weekend_from_weekday_without_bar():
    cal = pd.Series(pd.to_datetime(["2016-01-08", "2016-01-11", "2016-01-13"]))
    kept = pd.DataFrame({"date": pd.to_datetime(["2016-01-09", "2016-01-12", "2016-01-13"])})
    kept["trade_date"] = sd.align_trade_dates(kept["date"], cal)
    kept["moved"] = kept["trade_date"].ne(kept["date"])
    t = sg.g3_table(kept).set_index("year")
    assert t.loc[2016].tolist() == [3, 1, 1, 2]


# ------------------------------------------------------------------------------------ gates


def test_class_weights_inverse_frequency_from_train():
    w = sg.class_weights(pd.Series(["positive"] * 6 + ["negative"] * 3 + ["neutral"] * 1))
    assert w == pytest.approx({"negative": 10 / 9, "neutral": 10 / 3, "positive": 10 / 18})
    with pytest.raises(ValueError, match="neutral"):
        sg.class_weights(pd.Series(["positive", "negative"]))


def test_g2_identical_series_pass_and_a_bad_day_is_flagged():
    d = pd.to_datetime(["2016-01-04", "2016-01-05", "2016-01-06", "2016-01-07"])
    a = pd.DataFrame({"date": d, "close": [100.0, 101.0, 102.0, 101.5]})
    assert sg.g2_crosscheck(a, a, date(2003, 1, 1), 0.99, 0.005, 20)["status"] == "pass"
    b = a.assign(close=[100.0, 101.0, 103.0, 101.5])  # +1% on the 6th, back on the 7th
    r = sg.g2_crosscheck(a, b, date(2003, 1, 1), 0.99, 0.005, 20)
    assert r["flagged_first"] == ["2016-01-06", "2016-01-07"]
    assert r["share_flagged"] == pytest.approx(2 / 3)
    assert sg.g2_crosscheck(a, None, date(2003, 1, 1), 0.99, 0.005, 20) == {"status": "pending"}


def test_read_stooq_stops_before_the_stop_date(tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("Date,Open,High,Low,Close,Volume\n2026-01-08,1,2,0.5,1.5,0\n"
                    "2026-01-10,x\ngarbage\n", encoding="utf-8")  # fmt: skip
    df = sg.read_stooq(path, date(2026, 1, 10))
    assert df.to_dict("list") == {"date": [pd.Timestamp("2026-01-08")], "close": [1.5]}


def test_g5_counts_price_days_without_headlines():
    cal = pd.Series(pd.to_datetime(["2002-12-31", "2003-01-02", "2003-01-03", "2003-01-06",
                                    "2003-01-07"]))  # fmt: skip
    kept = pd.DataFrame({"trade_date": pd.to_datetime(["2003-01-02", "2003-01-02", "2003-01-06"])})
    t = sg.g5_table(kept, cal, date(2003, 1, 1)).set_index("year")
    assert t.loc[2003, "price days"] == 3  # to the last headline's trade date
    assert t.loc[2003, "zero-headline days"] == 1


def test_g1_tables_count_per_year_and_by_gap():
    df = headlines([("2015-01-01", "gold up"), ("2016-01-01", "Gold up!"),
                    ("2016-01-01", NEAR_A), ("2016-01-02", NEAR_B)])  # fmt: skip
    df.loc[1, "price_sentiment"] = "negative"
    out = sd.dedupe(df, 0.8, 3)
    t = sg.g1_table(out).set_index("year")
    assert t.loc[2016].tolist() == [3, 1, 1, 1]
    assert t.loc["all"].tolist() == [4, 1, 1, 2]
    g = sg.g1_exact_table(out).set_index("gap")
    assert g.loc["over 30 days"].tolist() == [1, 1] and g.loc["all"].tolist() == [1, 1]


def test_near_examples_quote_at_most_two_pairs():
    words = ("alpha", "beta", "gamma")  # one pair each: A + w vs B + w, Jaccard 9/10
    rows = [(f"2016-01-{d:02d}", f"{NEAR_A} {w}") for d, w in zip((1, 10, 20), words, strict=True)]
    rows += [(f"2016-01-{d:02d}", f"{NEAR_B} {w}") for d, w in zip((2, 11, 21), words, strict=True)]
    ex = sg.near_examples(sd.dedupe(headlines(rows), 0.8, 3))
    assert len(ex) == 2 and ex[0]["kept_date"] == "2016-01-01"


def test_url_date_and_date_shape():
    assert sd.url_date("http://m.com/story/gold-2016-01-28") == pd.Timestamp("2016-01-28")
    assert pd.isna(sd.url_date("http://m.com/story/gold-12016-01-28x"))
    assert pd.isna(sd.url_date("http://m.com/story/gold-2016-13-40"))
    assert sd.date_shape(" 0201-04-27") == "9999-99-99"
