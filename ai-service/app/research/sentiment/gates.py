"""Data gates G1-G5 (``docs/sentiment/PREREG_SENTIMENT.md`` §3) -> ``docs/sentiment/gates.md``.

    python -m app research sentiment gates

Reads what ``sentiment data`` wrote (it refuses if those files came from other raw data), writes
the report and the train-only class weights (G4) into ``app/config/sentiment.toml``. Counts only:
no statistic joins a headline or its label with a price or a volatility (G3 and G5 use the price
calendar, never a price). The report quotes at most four headline texts (two near-duplicate pairs;
licence CC BY-NC-ND 4.0, five at most in all)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.research.sentiment import data as sd

NEAR_EXAMPLES = 2  # pairs quoted in the report (four headline texts)


# ------------------------------------------------------------------------------------- helpers


def md_table(df: pd.DataFrame) -> str:
    """A pipe table (index dropped); floats are formatted by the caller."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


# ------------------------------------------------------------------------------------------ G1


def g1_table(gold: pd.DataFrame) -> pd.DataFrame:
    """Per year of the headline date: dated rows, exact and near duplicates removed, kept."""
    y = gold["date"].dt.year.rename("year")
    t = pd.DataFrame({
        "rows": gold.groupby(y).size(),
        "exact removed": gold.groupby(y)["dup_exact"].sum(),
        "near removed": gold.groupby(y)["dup_near"].sum(),
        "kept": gold.groupby(y)["keep"].sum(),
    }).astype(int)  # fmt: skip
    t.loc["all"] = t.sum()
    return t.reset_index()


def g1_exact_table(gold: pd.DataFrame) -> pd.DataFrame:
    """Exact duplicates by days to the kept headline they repeat (same day, 1-3, 4-30, over 30),
    with how many have a Price Sentiment different from the kept one."""
    by_id = gold.set_index("row_id")
    d = gold.loc[gold["dup_exact"]]
    kept = by_id.loc[d["dup_of"].to_numpy()]
    days = (d["date"].to_numpy() - kept["date"].to_numpy()) / np.timedelta64(1, "D")
    differs = d["price_sentiment"].to_numpy() != kept["price_sentiment"].to_numpy()
    bins = pd.cut(days, [-1, 0, 3, 30, np.inf], labels=["same day", "1-3 days", "4-30 days",
                                                       "over 30 days"])  # fmt: skip
    t = pd.DataFrame({"gap": bins, "n": 1, "label differs": differs})
    t = t.groupby("gap", observed=False).sum().astype(int)
    t.loc["all"] = t.sum()
    return t.reset_index()


def near_examples(gold: pd.DataFrame, k: int = NEAR_EXAMPLES) -> list[dict]:
    """The first ``k`` near-duplicates in (date, row_id) order with the kept headline they
    matched."""
    by_id = gold.set_index("row_id")
    out = []
    for r in gold.loc[gold["dup_near"]].head(k).itertuples():
        kept = by_id.loc[r.dup_of]
        out.append({
            "kept_date": str(kept["date"].date()), "kept": kept["headline"],
            "dropped_date": str(r.date.date()), "dropped": r.headline,
            "jaccard": float(r.dup_jaccard),
        })  # fmt: skip
    return out


# ------------------------------------------------------------------------------------------ G2


def read_stooq(path: Path, stop_before: date) -> pd.DataFrame:
    """Stooq daily CSV ``Date,Open,High,Low,Close[,Volume]``; reading stops at the first line
    dated on or after ``stop_before`` (nothing after it is read). Returns ``date``, ``close``."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = [h.strip().lower() for h in f.readline().split(",")]
        if header[:5] != ["date", "open", "high", "low", "close"]:
            raise ValueError(f"{path.name}: unexpected header {header}")
        for line in f:
            if not line.strip():
                continue
            d_text, _, rest = line.partition(",")
            d = date.fromisoformat(d_text.strip())
            if d >= stop_before:
                break
            rows.append((pd.Timestamp(d), float(rest.split(",")[3])))
    return pd.DataFrame(rows, columns=["date", "close"])


def g2_crosscheck(
    prices: pd.DataFrame,
    other: pd.DataFrame | None,
    first: date,
    min_corr: float,
    diff: float,
    n_list: int,
) -> dict:
    """Dukascopy (Sunday-merged) closes against a cross-check series on their common dates from
    ``first``: close correlation, log-return correlation (returns between consecutive common
    dates), share and first dates of |log-return difference| > ``diff``. ``other`` None: pending."""
    if other is None:
        return {"status": "pending"}
    a = prices.loc[prices["date"] >= pd.Timestamp(first), ["date", "close"]]
    j = a.merge(other[["date", "close"]], on="date", suffixes=("_duka", "_other"))
    j = j.sort_values("date").reset_index(drop=True)
    ra, rb = np.log(j["close_duka"]).diff(), np.log(j["close_other"]).diff()
    d = (ra - rb).abs()
    flagged = j.loc[d > diff, "date"].dt.date.astype(str).tolist()
    corr = float(j["close_duka"].corr(j["close_other"]))
    return {
        "status": "pass" if corr >= min_corr else "fail",
        "common_days": int(len(j)),
        "first": str(j["date"].iloc[0].date()) if len(j) else "",
        "last": str(j["date"].iloc[-1].date()) if len(j) else "",
        "close_corr": corr,
        "return_corr": float(ra.corr(rb)),
        "share_flagged": float((d > diff).sum() / d.notna().sum()) if d.notna().any() else 0.0,
        "flagged_count": len(flagged),
        "flagged_first": flagged[:n_list],
    }


# ------------------------------------------------------------------------------------------ G3


def g3_table(kept: pd.DataFrame) -> pd.DataFrame:
    """Kept headlines per year whose date has no price bar: on a weekend, on a weekday without a
    bar (holiday or missing day); both move to the next price day (``trade_date``)."""
    y = kept["date"].dt.year.rename("year")
    weekend = kept["date"].dt.day_of_week >= 5
    t = pd.DataFrame({
        "headlines": kept.groupby(y).size(),
        "weekend": (kept["moved"] & weekend).groupby(y).sum(),
        "weekday, no bar": (kept["moved"] & ~weekend).groupby(y).sum(),
        "moved": kept["moved"].groupby(y).sum(),
    }).astype(int)  # fmt: skip
    t.loc["all"] = t.sum()
    return t.reset_index()


# ------------------------------------------------------------------------------------------ G4


def class_weights(labels: pd.Series) -> dict[str, float]:
    """Inverse class frequency, normalised so the sample-weighted mean is 1: n / (K * n_c)."""
    n_c = labels.value_counts()
    missing = [c for c in sd.LABELS if n_c.get(c, 0) == 0]
    if missing:
        raise ValueError(f"no train headline with label {missing}")
    n, k = len(labels), len(sd.LABELS)
    return {c: float(n / (k * n_c[c])) for c in sd.LABELS}


def g4_table(kept: pd.DataFrame) -> pd.DataFrame:
    """Per split: kept headlines, training-label shares, and the share that were "none"."""
    rows = []
    for s in sd.SPLITS:
        part = kept.loc[kept["split"] == s]
        sh = part["label"].value_counts(normalize=True)
        rows.append({
            "split": s, "headlines": len(part),
            **{c: pct(sh.get(c, 0.0)) for c in sd.LABELS},
            "of which none": pct(part["is_none"].mean() if len(part) else 0.0),
            "first": str(part["date"].min().date()), "last": str(part["date"].max().date()),
        })  # fmt: skip
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------ G5


def g5_table(kept: pd.DataFrame, calendar: pd.Series, first: date) -> pd.DataFrame:
    """Price days from ``first`` with no kept headline on their ``trade_date``, per year (counts
    only). Years after the last headline are left out (every day there is empty)."""
    last = kept["trade_date"].max()
    cal = calendar[(calendar >= pd.Timestamp(first)) & (calendar <= last)]
    has = cal.isin(set(kept["trade_date"].dropna()))
    y = cal.dt.year.rename("year")
    t = pd.DataFrame({
        "price days": cal.groupby(y).size(),
        "zero-headline days": (~has).groupby(y).sum(),
    }).astype(int)  # fmt: skip
    t["share"] = (t["zero-headline days"] / t["price days"]).map(pct)
    return t.reset_index()


# ------------------------------------------------------------------------------- summaries


def label_shares(gold: pd.DataFrame) -> dict[str, float]:
    """Shares of the dataset's Price Sentiment (positive / negative / neutral / none)."""
    sh = gold["price_sentiment"].value_counts(normalize=True)
    return {c: float(sh.get(c, 0.0)) for c in ("positive", "negative", "neutral", "none")}


def summarise(processed: dict, cfg: sd.Config, other: pd.DataFrame | None) -> dict:
    """Every figure of the report, from what ``data`` wrote."""
    gold, man = processed["gold"], processed["manifest"]
    kept = gold.loc[gold["keep"]].copy()
    train = kept.loc[kept["split"] == "train", "label"]
    fpb = processed["fpb"]
    return {
        "manifest": man,
        "years": gold.groupby(gold["date"].dt.year).size(),
        "shares_all": label_shares(gold),
        "shares_kept": label_shares(kept),
        "g1": g1_table(gold),
        "near": near_examples(gold),
        "g1_exact": g1_exact_table(gold),
        "g2": g2_crosscheck(
            processed["prices"],
            other,
            cfg.price_first,
            cfg.g2_min_close_corr,
            cfg.g2_return_diff,
            cfg.g2_list,
        ),  # fmt: skip
        "g3": g3_table(kept),
        "g4": g4_table(kept),
        "weights": class_weights(train),
        "g5": g5_table(kept, processed["calendar"], cfg.price_first),
        "fpb_rows": len(fpb),
        "fpb_shares": fpb["label"].value_counts(normalize=True).reindex(sd.LABELS).fillna(0.0),
    }


# ---------------------------------------------------------------------------------------- report


def render(s: dict, cfg: sd.Config) -> str:
    man = s["manifest"]
    g, sp, pr = man["gold"], man["split"], man["prices"]
    out = [
        "# Gold-news sentiment: data gates G1-G5",
        "",
        "Generated by `python -m app research sentiment data` then `python -m app research "
        "sentiment gates` (`app/research/sentiment/`, config `app/config/sentiment.toml`). "
        "Registration: `docs/sentiment/PREREG_SENTIMENT.md` (DRAFT, not approved). Data work only: "
        "no model was trained, scored or loaded, and no figure here joins a headline or its label "
        "with a price or a volatility (G3 and G5 use the price calendar only).",
        "",
        "## Files (SHA-256)",
        "",
    ]
    files = pd.DataFrame([
        {"file": k, "path": f"`{cfg.files[k].path.relative_to(cfg.root).as_posix()}`",
         "status": v["status"], "sha256": f"`{v['sha256']}`" if v["sha256"] else "—"}
        for k, v in man["files"].items()
    ])  # fmt: skip
    out += [md_table(files), ""]

    shares = pd.DataFrame([
        {"rows": "all dated", **{k: pct(v) for k, v in s["shares_all"].items()}},
        {"rows": "kept (after G1)", **{k: pct(v) for k, v in s["shares_kept"].items()}},
    ])  # fmt: skip
    years = s["years"]
    out += [
        "## Gold headlines (Sinha and Khandait, arXiv:2009.04202; CC BY-NC-ND 4.0)",
        "",
        f"- Rows in the file: {g['rows_raw']:,}. Date format DD-MM-YYYY checked: "
        f"{g['day_field_gt12']:,} parsed rows have a day above 12, and where the article URL "
        f"carries a date it equals the file's date in {g['url_date_equal']:,} of "
        f"{g['url_date_rows']:,} rows.",
        f"- Dates that do not parse: {g['unparsable_dates']} rows, dropped (row ids in "
        "`processed/manifest.json`). Shapes: "
        + ", ".join(f"`{k}` {v}" for k, v in g["unparsable_shapes"].items())
        + f". {g['unparsable_url_date']} of them have a URL date and in "
        f"{g['unparsable_url_mmdd_match']} its month-day equals the raw value's: the year looks "
        "truncated (e.g. `0201-` for 201x). Not recovered (no rule registered).",
        f"- Date range: {g['first_date']} to {g['last_date']}.",
        f"- After exact dedupe: {g['rows_dated'] - g['dup_exact']:,}; after near dedupe (kept): "
        f"{g['kept']:,}.",
        "- Training label (PREREG §2.2): none -> neutral, `is_none` kept.",
        "",
        "Price Sentiment shares:",
        "",
        md_table(shares),
        "",
        "Rows per year (dated rows, before G1):",
        "",
        md_table(pd.DataFrame({"year": years.index, "rows": years.to_numpy()})),
        "",
    ]

    out += [
        "## G1 duplicates",
        "",
        f"Normalised text: lower case, every run of non-letters (punctuation, digits, symbols) "
        f"becomes a space, spaces collapsed. Exact duplicates of the normalised text dropped "
        f"(earliest date kept, file order on ties); then a headline whose token set has Jaccard "
        f">= {cfg.near_jaccard} with a kept headline dated up to {cfg.window_days} days earlier "
        f"(same day included) is dropped. Done before the split.",
        "",
        md_table(s["g1"]),
        "",
        "Exact duplicates by distance to the kept headline, and how many carry a different "
        "Price Sentiment from it (the kept label is the one used):",
        "",
        md_table(s["g1_exact"]),
        "",
        f"Near-duplicate examples (first {len(s['near'])} in date order):",
        "",
    ]
    for i, e in enumerate(s["near"], 1):
        out += [
            f'{i}. kept {e["kept_date"]}: "{e["kept"]}"; dropped {e["dropped_date"]}: '
            f'"{e["dropped"]}" (Jaccard {e["jaccard"]:.2f})'
        ]
    out += [
        "",
        f"**Split ({sp['chosen']}):** train <= {sp['train_last']}, validation to "
        f"{sp['val_last']}, test after. The default test split (2016+) holds "
        f"{sp['test_count_default']:,} kept headlines (rule: fallback if < {sp['min_test']:,}). "
        f"Kept headlines: train {sp['counts']['train']:,} / validation "
        f"{sp['counts']['validation']:,} / test {sp['counts']['test']:,}. Checked: no normalised "
        "text appears in two splits.",
        "",
    ]

    g2 = s["g2"]
    out += ["## G2 prices", ""]
    if g2["status"] == "pending":
        out += [
            "**Pending (MT5 D1 from Fadi).** The Stooq daily XAUUSD file could not be obtained "
            "(2026-11-18: the download URL answered 404). Pass rule when run: daily close "
            f"correlation >= {cfg.g2_min_close_corr} on common dates from {cfg.price_first}.",
            "",
        ]
    else:
        out += [
            f"Dukascopy (Sunday merged) vs Stooq, {g2['common_days']:,} common dates "
            f"{g2['first']} to {g2['last']}: close correlation {g2['close_corr']:.5f}, log-return "
            f"correlation {g2['return_corr']:.4f}, days with |log-return difference| > "
            f"{pct(cfg.g2_return_diff)}: {g2['flagged_count']} ({pct(g2['share_flagged'])}). "
            f"**{g2['status'].upper()}** (rule: close correlation >= {cfg.g2_min_close_corr}).",
            "",
            f"First flagged dates: {', '.join(g2['flagged_first']) or 'none'}.",
            "",
        ]
    out += [
        f"Dukascopy XAUUSD D1 bid, bars read: {pr['bars_raw']:,} (to the last bar before "
        f"{cfg.price_stop}, the lockbox start; the reader stops there). Sunday bars: "
        f"{pr['sunday_bars']:,}, merged into Monday {pr['sunday_merged']:,}, dropped (no Monday) "
        f"{pr['sunday_dropped']:,}; Saturday bars {pr['saturday_bars']}. From {cfg.price_first}: "
        f"{pr['bars_from_first']:,} bars ({pr['first_price_day']} to {pr['last_price_day']}), "
        f"OHLC violations after the merge {pr['ohlc_violations']}, Garman-Klass variance <= 0 "
        f"(log_gk NaN) {pr['gk_nonpositive']}.",
        "",
    ]

    out += [
        "## G3 day alignment",
        "",
        "Kept headlines dated on a day without a Dukascopy bar (00:00 UTC days; Sunday bars are "
        "merged into Monday, so Sunday is never a price day) move to the next price day "
        "(`trade_date`). The calendar includes 2000-2002 for this alignment only.",
        "",
        md_table(s["g3"]),
        "",
    ]

    w = s["weights"]
    out += [
        "## G4 label balance",
        "",
        md_table(s["g4"]),
        "",
        "Class weights from train only (n / (K n_c), written to `sentiment.toml`): "
        + ", ".join(f"{c} {w[c]:.4f}" for c in sd.LABELS)
        + ".",
        "",
    ]

    out += [
        "## G5 coverage",
        "",
        f"Price days from {cfg.price_first} to the last headline's trade date with no kept "
        "headline (counts only).",
        "",
        md_table(s["g5"]),
        "",
    ]

    fs = s["fpb_shares"]
    out += [
        "## FinancialPhraseBank (Malo et al. 2014; Sentences_AllAgree; CC BY-NC-SA 3.0)",
        "",
        f"Rows {s['fpb_rows']:,}: "
        + ", ".join(f"{c} {pct(fs[c])}" for c in sd.LABELS)
        + ". Used only for stage-1 training (S3); its labels are from an equity investor's "
        "point of view.",
        "",
    ]
    return "\n".join(out)


def run(cfg: sd.Config) -> str:
    """Verify the raw files, read the processed ones, write the report and the class weights."""
    status = sd.verify_files(cfg)
    processed = sd.load_processed(cfg)
    other = None
    if status.get("stooq") == "ok":
        other = read_stooq(cfg.files["stooq"].path, cfg.price_stop)
    s = summarise(processed, cfg, other)
    text = render(s, cfg)
    cfg.report.parent.mkdir(parents=True, exist_ok=True)
    cfg.report.write_text(text, encoding="utf-8", newline="\n")
    sd.write_class_weights(cfg.path, s["weights"])
    return text
