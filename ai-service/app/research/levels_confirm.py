"""Addendum 2, H_L1: the single reading of the level-break mechanism on the confirmation
instruments (docs/strategies/ADDENDUM_2_LEVEL_BREAK.md).

    python -m app research levels-confirm import --raw-dir "<MT5 Common>/Files/history"
    python -m app research levels-confirm run          # once; refused if it was read before

**import** parses the six M1 exports (``tools/mt5/ExportHistory.mq5``) with the research
importer, its clock checks and the specs of section 4, into ``data/confirm/<SYMBOL>/`` (untracked).
The specs live here, not in ``app/config``, which stays as frozen at ``b9ca2a8``. It reads the bars
only to build the store: no level, touch or outcome is computed.

**run** reads the store once and writes ``docs/strategies/levels_confirm.md``. It is refused while
that report exists, while the addendum is not registered (approval date filled) or differs from
its commit, or while this file differs from its commit. The rules are those of section 3 and of
``tools/research/levels_explore.py``: levels PDH, PDL, 5DH, 5DL and round numbers; placebo levels;
the first touch of the day in 02:00-15:59 New York on weekdays; D = ATR(14) of the last closed 1h
bar; first passage within 48 bars. Touches from 2018-01-01; bars stop at the lockbox start
(2026-01-10). Decision (section 5): the pooled real-minus-placebo bounce rate below zero with a
one-sided p < 0.05 (4-week block bootstrap from 2018-01-01, B = 20,000, percentile, seed
20261104) and below zero on at least 4 of the 6 instruments. H_L2 (the trade) is judged in the MT5
Strategy Tester, not here."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

from app.config import Instrument, splits
from app.data.exports import name_fields
from app.data.importer import import_symbol
from app.strategies import frames as F
from app.strategies.cli import OUT_DIR, ROOT

ADDENDUM = OUT_DIR / "ADDENDUM_2_LEVEL_BREAK.md"
REPORT = OUT_DIR / "levels_confirm.md"
STORE = ROOT / "data" / "confirm"
THIS = "ai-service/app/research/levels_confirm.py"
SEED = 20261104
B = 20_000
HZ = 48
START = pd.Timestamp("2018-01-01", tz="UTC")
WARM = pd.Timestamp("2017-06-01", tz="UTC")


def _fx(symbol: str, point: float, decimals: int, quote: str) -> Instrument:
    return Instrument(symbol, point, decimals, 100_000, quote, "17:00", "17:00")


# Section 4: specs from the account (history_meta*.json of 2026-11-04), in the addendum's order.
INSTRUMENTS: dict[str, Instrument] = {
    "NZDUSD": _fx("NZDUSD", 0.00001, 5, "USD"),
    "USDCHF": _fx("USDCHF", 0.00001, 5, "CHF"),
    "EURJPY": _fx("EURJPY", 0.001, 3, "JPY"),
    "GBPJPY": _fx("GBPJPY", 0.001, 3, "JPY"),
    "EURGBP": _fx("EURGBP", 0.00001, 5, "GBP"),
    "XAGUSD": Instrument("XAGUSD", 0.001, 3, 5000, "USD", "18:00", "17:00", ("17:00", "18:00")),
}
# Section 3: the round-number step of each instrument.
STEP = {"NZDUSD": 0.005, "USDCHF": 0.005, "EURGBP": 0.005, "EURJPY": 0.5, "GBPJPY": 0.5,
        "XAGUSD": 0.25}  # fmt: skip


# --- preconditions --------------------------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def preconditions(report: Path = REPORT, addendum: Path = ADDENDUM) -> str:
    """The commit holding the registered addendum, or an error that refuses the reading."""
    if report.exists():
        raise PermissionError(f"the confirmation data were read already ({report.name}); once only")
    text = addendum.read_text(encoding="utf-8")
    if not re.search(r"\| Approval date \| \d{4}-\d{2}-\d{2} \|", text):
        raise PermissionError("Addendum 2 is not approved (approval date empty)")
    rel = f"ai-service/docs/strategies/{addendum.name}"
    for path in (rel, THIS):
        if _git("diff", "--quiet", "HEAD", "--", f"../{path}").returncode != 0:
            raise PermissionError(f"{path} differs from its commit: commit it before the reading")
        if not _git("log", "-1", "--format=%H", "--", f"../{path}").stdout.strip():
            raise PermissionError(f"{path} is not committed")
    return _git("log", "-1", "--format=%H", "--", f"../{rel}").stdout.strip()


# --- the rules (section 3; the same as tools/research/levels_explore.py) ---------------------


def wilder(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - prev), np.abs(lo - prev)], axis=1)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def first_passage(hi, lo, i, lv, d, up):
    """Outcome ('break', 'bounce', 'none', 'ambiguous') of touches at bars ``i`` of levels ``lv``
    approached from below (``up``) or above, and the continuation after a break (1, 0 or NaN)."""
    s = np.where(up, 1.0, -1.0)
    brk_t, bnc_t = lv + s * d, lv - s * d
    brk0 = np.where(up, hi[i] >= brk_t, lo[i] <= brk_t)  # the touch bar counts for the break only
    H, L = swv(hi, HZ)[i + 1], swv(lo, HZ)[i + 1]
    brk = np.where(up[:, None], H >= brk_t[:, None], L <= brk_t[:, None])
    bnc = np.where(up[:, None], L <= bnc_t[:, None], H >= bnc_t[:, None])
    fb = np.where(brk.any(1), brk.argmax(1), HZ)
    fn = np.where(bnc.any(1), bnc.argmax(1), HZ)
    tie = np.where(fb == HZ, "none", "ambiguous")
    out = np.where(fb < fn, "break", np.where(fn < fb, "bounce", tie))
    out = np.where(brk0, "break", out)
    jb = np.where(brk0, i, i + 1 + np.minimum(fb, HZ - 1))
    k = np.minimum(jb + 1, len(hi) - HZ)
    H2, L2 = swv(hi, HZ)[k], swv(lo, HZ)[k]
    far = lv + 2 * s * d
    go = np.where(up[:, None], H2 >= far[:, None], L2 <= far[:, None])
    ret = np.where(up[:, None], L2 <= lv[:, None], H2 >= lv[:, None])
    fg = np.where(go.any(1), go.argmax(1), HZ)
    fr = np.where(ret.any(1), ret.argmax(1), HZ)
    cont = np.where(fg < fr, 1.0, np.where(fr < fg, 0.0, np.nan))
    return out, np.where(out == "break", cont, np.nan)


def touches(fr: dict[str, pd.DataFrame], sym: str, step: float, rng) -> pd.DataFrame:
    """Every first touch of the day of the real and placebo levels of one instrument, with its
    outcome. ``rng`` draws the placebo offsets (the same generator across instruments, in order)."""
    m, h1, d1 = fr["5m"], fr["1h"], fr["D1"]
    hi, lo, cl = (m[k].to_numpy() for k in ("high", "low", "close"))
    n = len(m)
    prev = np.r_[np.nan, cl[:-1]]
    a1 = wilder(*(h1[k].to_numpy() for k in ("high", "low", "close")))
    k1 = np.searchsorted(h1["close_utc"].to_numpy(), m["ts_utc"].to_numpy(), "right") - 1
    D = np.where(k1 >= 0, a1[np.maximum(k1, 0)], np.nan)
    ad = wilder(*(d1[k].to_numpy() for k in ("high", "low", "close")))
    kd = np.searchsorted(d1["ts_utc"].to_numpy(), m["ts_utc"].to_numpy(), "right") - 1
    dh, dl = d1["high"].to_numpy(), d1["low"].to_numpy()
    pdh, pdl = np.r_[np.nan, dh[:-1]], np.r_[np.nan, dl[:-1]]
    h5 = pd.Series(dh).rolling(5).max().shift(1).to_numpy()
    l5 = pd.Series(dl).rolling(5).min().shift(1).to_numpy()
    atrd = np.r_[np.nan, ad[:-1]]
    ny = m["ts_utc"].dt.tz_convert("America/New_York")
    ok = ((ny.dt.day_of_week < 5) & ny.dt.hour.between(2, 15)).to_numpy().copy()
    ok &= (m["ts_utc"] >= START).to_numpy() & (np.arange(n) < n - 2 * HZ - 2)
    ok &= np.isfinite(D) & (kd >= 6)

    def day_levels(level_of_day: np.ndarray, name: str, placebo: bool) -> pd.DataFrame:
        lv = level_of_day[np.maximum(kd, 0)]
        up = (prev < lv) & (hi >= lv)
        dn = (prev > lv) & (lo <= lv)
        idx = np.flatnonzero(ok & (up | dn) & np.isfinite(lv))
        first = pd.Series(idx).groupby(kd[idx]).min().to_numpy()
        return pd.DataFrame({"i": first, "lv": lv[first], "up": up[first], "kind": name,
                             "placebo": placebo})  # fmt: skip

    ev = []
    for name, arr in (("PDH", pdh), ("PDL", pdl), ("5DH", h5), ("5DL", l5)):
        ev.append(day_levels(arr, name, False))
        off = rng.uniform(0.3, 1.0, len(arr)) * rng.choice([-1.0, 1.0], len(arr)) * atrd
        ev.append(day_levels(arr + off, name, True))
    for placebo, shift in ((False, 0.0), (True, step / 2)):
        parts = []
        for up_side in (True, False):
            base = prev - shift
            lvl = (np.ceil(base / step) if up_side else np.floor(base / step)) * step + shift
            cross = (prev < lvl) & (hi >= lvl) if up_side else (prev > lvl) & (lo <= lvl)
            idx = np.flatnonzero(ok & cross)
            parts.append(pd.DataFrame({"i": idx, "lv": lvl[idx], "up": up_side, "day": kd[idx]}))
        r = pd.concat(parts).sort_values("i").drop_duplicates(["day", "lv"]).drop(columns="day")
        ev.append(r.assign(kind="ROUND", placebo=placebo))
    e = pd.concat(ev, ignore_index=True)
    i = e["i"].to_numpy()
    out, cont = first_passage(hi, lo, i, e["lv"].to_numpy(), D[i], e["up"].to_numpy())
    t = pd.to_datetime(m["ts_utc"].to_numpy()[i], utc=True)
    spread = m["spread_mean"].to_numpy()[i] if "spread_mean" in m else np.full(len(i), np.nan)
    return e.assign(symbol=sym, outcome=out, cont=cont, spread_d=spread / D[i], t=t)


# --- the decision (section 5) ----------------------------------------------------------------


@dataclass(frozen=True)
class Diff:
    n_real: int
    rate_real: float
    n_placebo: int
    rate_placebo: float
    diff: float
    lo: float
    hi: float
    p_below: float  # one-sided p of "real - placebo < 0"


def diff_test(g: pd.DataFrame, col: str, rng, boot: int = B) -> Diff:
    """Real minus placebo rate of ``col`` with a 4-week block bootstrap from 2018-01-01."""
    x = g.dropna(subset=[col])
    block = ((x["t"] - START).dt.days // 28).astype(int)
    agg = x.groupby([block, "placebo"])[col].agg(["sum", "size"]).unstack(fill_value=0)
    full = pd.MultiIndex.from_product([["sum", "size"], [False, True]])
    agg = agg.reindex(columns=full, fill_value=0)
    if agg[("size", False)].sum() == 0 or agg[("size", True)].sum() == 0:
        n = (int(agg[("size", False)].sum()), int(agg[("size", True)].sum()))
        return Diff(n[0], np.nan, n[1], np.nan, np.nan, np.nan, np.nan, np.nan)
    s_r, n_r = agg[("sum", False)].to_numpy(), agg[("size", False)].to_numpy()
    s_p, n_p = agg[("sum", True)].to_numpy(), agg[("size", True)].to_numpy()
    k = rng.integers(0, len(agg), (boot, len(agg)))
    dif = s_r[k].sum(1) / n_r[k].sum(1) - s_p[k].sum(1) / n_p[k].sum(1)
    real, plac = s_r.sum() / n_r.sum(), s_p.sum() / n_p.sum()
    lo, hi = np.percentile(dif, [2.5, 97.5])
    p = (1 + int((dif >= 0).sum())) / (boot + 1)
    return Diff(int(n_r.sum()), real, int(n_p.sum()), plac, real - plac, lo, hi, p)


def outcomes(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(bounce=np.where(d.outcome == "bounce", 1.0,
                                    np.where(d.outcome == "break", 0.0, np.nan)))  # fmt: skip


def decide(pooled: Diff, per_instrument: dict[str, Diff]) -> str:
    below = sum(r.diff < 0 for r in per_instrument.values())
    if pooled.p_below < 0.05 and pooled.diff < 0 and below >= 4:
        return "H_L1 passed"
    return "H_L1 not passed"


# --- report ----------------------------------------------------------------------------------


def _row(name: str, r: Diff, p: bool = False) -> str:
    tail = f" | {r.p_below:.4f}" if p else ""
    return (f"| {name} | {r.n_real:,} | {r.rate_real:.3f} | {r.n_placebo:,} | {r.rate_placebo:.3f} "
            f"| {r.diff * 100:+.1f} ({r.lo * 100:+.1f} to {r.hi * 100:+.1f}){tail} |")  # fmt: skip


def render(d: pd.DataFrame, rng, commit: str, head: str, run_date: str, boot: int = B) -> str:
    pooled = diff_test(d, "bounce", rng, boot)
    per = {s: diff_test(g, "bounce", rng, boot) for s, g in d.groupby("symbol", sort=False)}
    result = decide(pooled, per)
    hdr = ("| {} | Touches (real) | Bounce rate | Touches (placebo) | Bounce rate "
           "| Real - placebo, points (95%){} |")  # fmt: skip
    sep = "| --- | --- | --- | --- | --- | --- |"
    lines = [
        "# Addendum 2: the level-break reading on the confirmation instruments",
        "",
        f"_Generated by `python -m app research levels-confirm run` on {run_date}, once. Addendum "
        f"committed at `{commit}`, code at `{head}`. Touches from 2018-01-01, bars to the lockbox "
        "start (2026-01-10); the lockbox was not read. Rules: `ADDENDUM_2_LEVEL_BREAK.md` section "
        f"3; 4-week block bootstrap, B = {boot:,}, seed {SEED}. H_L2 (the trade) is judged in the "
        "MT5 Strategy Tester and reported separately._",
        "",
        "## Decision (section 5)",
        "",
        hdr.format("Set", " | one-sided p"),
        sep + " --- |",
        _row("All six, pooled", pooled, p=True),
        "",
        f"Instruments below their placebo: {sum(r.diff < 0 for r in per.values())} of {len(per)} "
        "(the rule needs at least 4).",
        "",
        f"**{result}.**",
        "",
        "## Per instrument",
        "",
        hdr.format("Instrument", ""),
        sep,
        *[_row(s, r) for s, r in per.items()],
        "",
        "## Reported, not decided on",
        "",
        "Bounce rate by level type, all instruments:",
        "",
        hdr.format("Level", ""),
        sep,
        *[_row(k, diff_test(g, "bounce", rng, boot)) for k, g in d.groupby("kind")],
        "",
        "Continuation after a break (2D through before back to the level), real minus placebo:",
        "",
        hdr.format("Set", "").replace("Bounce rate", "Continuation"),
        sep,
        *[_row(k, diff_test(g, "cont", rng, boot)) for k, g in [*d.groupby("kind"), ("All", d)]],
        "",
        "Bounce rate by year, all instruments (real / placebo):",
        "",
        "| Year | Real | Placebo |",
        "| --- | --- | --- |",
    ]
    yr = d.groupby([d["t"].dt.year, "placebo"])["bounce"].mean().unstack()
    lines += [f"| {y} | {r[False]:.3f} | {r[True]:.3f} |" for y, r in yr.iterrows()]
    mix = {p: d[d.placebo == p].outcome.value_counts(normalize=True).round(3).to_dict()
           for p in (False, True)}  # fmt: skip
    sp = d[~d.placebo].groupby("symbol", sort=False)["spread_d"].mean()
    lines += [
        "",
        f"Outcome mix, real levels: {mix[False]}; placebo: {mix[True]}.",
        "",
        "Mean recorded spread at the touch, in D (descriptive; the trade's cost comes from the "
        "tester): " + ", ".join(f"{s} {v:.3f}" for s, v in sp.items()) + ".",
    ]
    return "\n".join(lines) + "\n"


# --- commands --------------------------------------------------------------------------------


def find_exports(raw_dir: Path) -> dict[str, Path]:
    found = {}
    for p in sorted(raw_dir.glob("*.csv")):
        f = name_fields(p.name)
        if f.get("timeframe") == "M1" and f["symbol"] in INSTRUMENTS:
            found[f["symbol"]] = p
    return found


def load(store: Path = STORE) -> dict[str, dict[str, pd.DataFrame]]:
    lockbox = pd.Timestamp(splits().lockbox_start, tz="UTC")
    return {s: F.load(s, WARM, lockbox, store) for s in INSTRUMENTS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research levels-confirm")
    ap.add_argument("step", choices=("import", "run"))
    ap.add_argument("--raw-dir", type=Path)
    ap.add_argument("--store", type=Path, default=STORE)
    args = ap.parse_args(argv)
    if args.step == "import":
        if args.raw_dir is None:
            print("refused: --raw-dir is needed", file=sys.stderr)
            return 2
        found = find_exports(args.raw_dir)
        missing = [s for s in INSTRUMENTS if s not in found]
        if missing:
            print(f"refused: no M1 export for {missing} in {args.raw_dir}", file=sys.stderr)
            return 2
        for s in INSTRUMENTS:
            r = import_symbol(s, found[s], args.store, INSTRUMENTS[s])
            p = r["parse"]
            print(f"{s}: {p['rows_kept']:,} M1 bars kept, {p['rows_rejected']} rejected, "
                  f"{r['range_utc'][0]} -> {r['range_utc'][1]}, clock segments "
                  f"{len(r['clock_segments'])}, stopped at lockbox: "
                  f"{r['input']['stopped_at_lockbox']}")  # fmt: skip
        return 0
    try:
        commit = preconditions()
    except PermissionError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    rng = np.random.default_rng(SEED)
    frames = load(args.store)
    d = outcomes(pd.concat([touches(frames[s], s, STEP[s], rng) for s in INSTRUMENTS],
                           ignore_index=True))  # fmt: skip
    head = _git("rev-parse", "HEAD").stdout.strip()
    run_date = pd.Timestamp.now(tz="UTC").date().isoformat()
    REPORT.write_text(render(d, rng, commit, head, run_date), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
