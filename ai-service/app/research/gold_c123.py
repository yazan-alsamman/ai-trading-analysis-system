"""Gold: three continuation candidates from the building-block research
(``docs/strategies/GOLD_C123.md``, registered 2026-11-11).

    python -m app research gold-c123 build --export <GOLD M1>

- **C1:** at 08:00 London and 09:30 New York, the trading-day return since the same checkpoint,
  over its 60-day standard deviation (TS); enter with it when 0.5 <= |TS| <= 2 (BAND) or >= 0.5
  (OPEN); exit at 12:00 London / 16:45 New York.
- **C2:** at 12:30 New York, the day's move since its first bar over its 60-day standard
  deviation (z); |z| >= 1.5: enter with it; exit 13:35 (A) or 16:45 (B) New York.
- **C3:** 15 minutes after NFP / CPI / the Fed (TOP3; TOP5 adds core PCE and GDP), a move of at
  least the same-clock noise; enter with it; SL beyond the post-release extreme; exit 16:45.

SL 1 x ATR(14, 1h) for C1 and C2; no target; cost cap 0.10; a +/-15-minute gate around
high-importance USD releases (not C3)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs
from app.research import gold_time as gt

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "data" / "processed" / "calendar.parquet"
REPORT = gl.OUT_DIR / "gold_c123_result.md"  # not gold_c123.md: GOLD_C123.md on Windows
TUNE_END = gc.TUNE_END
LONDON, NY = "Europe/London", "America/New_York"
LOOK, NOISE_DAYS, CAP, GATE = 60, 20, 0.10, 15
TOP3 = ("Nonfarm Payrolls", "CPI m/m", "Fed Interest Rate Decision")
TOP5 = (*TOP3, "Core PCE Price Index m/m", "GDP q/q")
MAX_CORR = 0.2
MIN_TRADES = {"C1": 300, "C2": 300, "C3": 100}
CELLS = {"C1": ("BAND", "OPEN"), "C2": ("A", "B"), "C3": ("TOP3", "TOP5")}


# --- clock helpers --------------------------------------------------------------------------------


def day_dates(cx: gl.Ctx, ck: gt.Clock) -> pd.Series:
    """Each trading day's New York date (of its last bar), as 'YYYY-MM-DD'; '' when empty."""
    out = np.full(ck.n_days, "", dtype=object)
    ok = cx.day_idx >= 0
    last = pd.Series(np.arange(len(cx.c))[ok]).groupby(cx.day_idx[ok]).max()
    d = cx.ny_day[last.to_numpy()]
    out[last.index.to_numpy()] = [f"{x // 10000:04d}-{x // 100 % 100:02d}-{x % 100:02d}" for x in d]
    return pd.Series(out)


def at_local(cx: gl.Ctx, dates: pd.Series, hhmm: str, tz: str) -> np.ndarray:
    """Per trading day: the 5m bar closing at ``hhmm`` ``tz`` on its New York date; -1: none."""
    out = np.full(len(dates), -1)
    ok = dates.to_numpy() != ""
    loc = pd.to_datetime(dates[ok] + " " + hhmm).dt.tz_localize(
        tz, ambiguous="NaT", nonexistent="NaT"
    )
    when = loc.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    close = cx.m["close_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    k = np.searchsorted(close, when)
    k = np.minimum(k, len(close) - 1)
    hit = (close[k] == when) & ~np.isnat(when)
    idx = np.flatnonzero(ok)
    out[idx[hit]] = k[hit]
    return out


def zscore(x: np.ndarray, look: int = LOOK) -> np.ndarray:
    """x over the standard deviation of the previous ``look`` valid values (NaN skipped)."""
    s = pd.Series(x)
    valid = s.dropna()
    sd = valid.shift(1).rolling(look, min_periods=look).std()
    out = np.full(len(x), np.nan)
    out[valid.index.to_numpy()] = (valid / sd).to_numpy()
    return out


def release_times(cal: pd.DataFrame | None) -> np.ndarray:
    if cal is None:
        return np.array([], dtype="datetime64[ns]")
    hi = cal[(cal["currency"] == "USD") & (cal["importance"] == 3)]["ts_utc"]
    return np.sort(hi.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]"))


def gated(cx: gl.Ctx, k: np.ndarray, rel: np.ndarray) -> np.ndarray:
    """True where bar k's close is within 15 minutes of a high-importance USD release."""
    if not len(rel) or not len(k):
        return np.zeros(len(k), bool)
    t = cx.m["close_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")[k]
    j = np.searchsorted(rel, t)
    near = np.full(len(k), np.inf)
    for jj in (j - 1, j):
        okj = (jj >= 0) & (jj < len(rel))
        d = np.abs((t[okj] - rel[jj[okj]]).astype("timedelta64[s]").astype(float))
        near[okj] = np.minimum(near[okj], d)
    return near <= GATE * 60


# --- signals --------------------------------------------------------------------------------------


def _sig(cx: gl.Ctx, name: str, k: np.ndarray, d: np.ndarray, risk: np.ndarray,
         end: np.ndarray) -> pd.DataFrame:  # fmt: skip
    ok = (k >= 0) & (end > k) & (d != 0) & np.isfinite(risk) & (risk > 0)
    k, d, risk, end = k[ok], d[ok], risk[ok], end[ok]
    ok = (cx.spread[k] + gl.COMMISSION) / risk <= CAP
    ok &= cx.weekday[end] < 5
    k, d, risk, end = k[ok], d[ok], risk[ok], end[ok]
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[k], utc=True)
    s = pd.DataFrame({"strategy": name, "i": k, "dir": d.astype(float), "entry": cx.c[k],
                      "risk": risk, "tp_r": np.nan, "end": end})  # fmt: skip
    return s[t >= gl.START].sort_values("i").reset_index(drop=True)


def c1(cx: gl.Ctx, ck: gt.Clock, dates: pd.Series, cell: str, rel: np.ndarray) -> pd.DataFrame:
    legs = []
    for k, end in (
        (at_local(cx, dates, "08:00", LONDON), at_local(cx, dates, "12:00", LONDON)),
        (ck.at(gt.hm(9, 30)), None),
    ):
        c = np.where(k >= 0, cx.c[np.maximum(k, 0)], np.nan)
        prev = pd.Series(c).ffill().shift(1).to_numpy()  # the last valid checkpoint before
        r = np.log(c / prev)
        ts = zscore(r)
        a = np.abs(ts)
        take = (a >= 0.5) & ((a <= 2.0) if cell == "BAND" else True)
        d = np.where(take, np.sign(ts), 0.0)
        e = np.where(k >= 0, cx.deadline[np.maximum(k, 0)], -1) if end is None else end
        risk = np.where(k >= 0, cx.atr1h[np.maximum(k, 0)], np.nan)
        keep = ~gated(cx, np.maximum(k, 0), rel) & (k >= 0)
        legs.append(_sig(cx, f"C1-{cell}", np.where(keep, k, -1), d, risk, e))
    return pd.concat(legs, ignore_index=True).sort_values("i").reset_index(drop=True)


def c2(cx: gl.Ctx, ck: gt.Clock, cell: str, rel: np.ndarray) -> pd.DataFrame:
    k = ck.at(gt.hm(12, 30))
    f = ck.first
    ok = (k >= 0) & (f >= 0)
    r = np.where(ok, np.log(cx.c[np.maximum(k, 0)] / cx.o[np.maximum(f, 0)]), np.nan)
    z = zscore(r)
    d = np.where(np.abs(z) >= 1.5, np.sign(z), 0.0)
    end = (
        ck.at(gt.hm(13, 35)) if cell == "A" else np.where(k >= 0, cx.deadline[np.maximum(k, 0)], -1)
    )
    risk = np.where(k >= 0, cx.atr1h[np.maximum(k, 0)], np.nan)
    keep = ~gated(cx, np.maximum(k, 0), rel) & ok
    return _sig(cx, f"C2-{cell}", np.where(keep, k, -1), d, risk, end)


def c3(cx: gl.Ctx, cal: pd.DataFrame, cell: str) -> pd.DataFrame:
    names = TOP3 if cell == "TOP3" else TOP5
    ev = cal[(cal["currency"] == "USD") & cal["event"].isin(names)][["ts_utc", "event"]]
    ev = ev.drop_duplicates("ts_utc").sort_values("ts_utc")
    close = cx.m["close_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    rel = ev["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")

    def bar(when: np.ndarray) -> np.ndarray:
        k = np.minimum(np.searchsorted(close, when), len(close) - 1)
        return np.where(close[k] == when, k, -1)

    base = bar(rel)
    k = bar(rel + np.timedelta64(15, "m"))
    rows = []
    # noise: the same clock window on the previous 20 trading days (by New York minute)
    ny_min = pd.Series(rel).dt.tz_localize("UTC").dt.tz_convert(NY)
    ny_min = (ny_min.dt.hour * 60 + ny_min.dt.minute).to_numpy()
    ck = gt.Clock(cx)
    noise_cache: dict[int, np.ndarray] = {}
    for q in range(len(rel)):
        b, kk = int(base[q]), int(k[q])
        if b < 0 or kk < 0 or kk <= b:
            continue
        m = int(ny_min[q])
        if m not in noise_cache:
            a0, a1 = ck.at(m), ck.at(m + 15)
            ok = (a0 >= 0) & (a1 >= 0)
            mv = np.where(ok, np.abs(cx.c[np.maximum(a1, 0)] - cx.c[np.maximum(a0, 0)]), np.nan)
            s = pd.Series(mv)
            noise_cache[m] = s.shift(1).rolling(NOISE_DAYS, min_periods=10).mean().to_numpy()
        day = int(cx.day_idx[kk])
        noise = noise_cache[m][day] if 0 <= day < len(noise_cache[m]) else np.nan
        move = cx.c[kk] - cx.c[b]
        if not np.isfinite(noise) or noise <= 0 or abs(move) < noise:
            continue
        d = np.sign(move)
        ext = cx.lo[b + 1 : kk + 1].min() if d > 0 else cx.h[b + 1 : kk + 1].max()
        sl = ext - d * 0.1 * cx.atr5[kk]
        risk = d * (cx.c[kk] - sl)
        end = int(cx.deadline[kk])
        if ev["event"].iloc[q] == "Fed Interest Rate Decision":
            end = min(end, kk + 36)
        rows.append((kk, d, risk, end))
    if not rows:
        return _sig(cx, f"C3-{cell}", np.array([], int), np.array([]), np.array([]),
                    np.array([], int))  # fmt: skip
    a = np.array(rows, dtype=float)
    return _sig(cx, f"C3-{cell}", a[:, 0].astype(int), a[:, 1], a[:, 2], a[:, 3].astype(int))


def run(cx: gl.Ctx, sig: pd.DataFrame) -> pd.DataFrame:
    return gn.with_day(gs.finish(gl.simulate(sig, cx, "M0"), cx), cx)


def all_cells(cx: gl.Ctx, cal: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ck = gt.Clock(cx)
    dates = day_dates(cx, ck)
    rel = release_times(cal)
    out = {}
    for cell in CELLS["C1"]:
        out[f"C1-{cell}"] = run(cx, c1(cx, ck, dates, cell, rel))
    for cell in CELLS["C2"]:
        out[f"C2-{cell}"] = run(cx, c2(cx, ck, cell, rel))
    for cell in CELLS["C3"]:
        out[f"C3-{cell}"] = run(cx, c3(cx, cal, cell))
    return out


def t_stat(t: pd.DataFrame) -> float:
    x = t["net_slip"]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 else np.nan


def build(export: Path) -> str:
    cal = pd.read_parquet(CAL)
    cx = gl.context(gl.load())
    cells = all_cells(cx, cal)
    days = len(np.unique(cx.day_idx[(cx.m["close_utc"] >= gl.START).to_numpy()]))
    lines = [
        "# Gold: three continuation candidates (C1-C3), XAUUSD and FxPro",
        "",
        "_`python -m app research gold-c123 build`, registered in `GOLD_C123.md` (2026-11-11). "
        "XAUUSD 5m 2012 to 2026-01-09, then FxPro GOLD; cost = spread + $0.07, slip $0.10 on SL "
        "exits; net R with slip._",
        "",
        "| Cell | Trades a day | Tune trades | Tune net (with slip) | Tune years + | Check trades "
        "| Check net (with slip) | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    chosen = {}
    for name, t in cells.items():
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        cand = name.split("-")[0]
        elig = a["net"] > 0 and a["years_pos"] >= 0.6 and a["trades"] >= MIN_TRADES[cand]
        mark = "yes" if elig else ""
        lines.append(f"| {name} | {len(t) / days:.2f} | {a['trades']:,} | {a['net']:+.3f} "
                     f"({a['net_slip']:+.3f}) | {a['years_pos']:.0%} | {b['trades']:,} "
                     f"| {b['net']:+.3f} ({b['net_slip']:+.3f}) | {mark} |")  # fmt: skip
        if elig and (cand not in chosen or a["net"] > chosen[cand][1]):
            chosen[cand] = (name, a["net"])
    fx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    fcells = all_cells(fx, cal)
    since = pd.to_datetime(fx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    day = gn.day_strategies(fx)
    start = np.datetime64(gv.FX_START.tz_convert(None))
    day = {k: v[since[v["i"]] >= start] for k, v in day.items()}
    lines += ["", "## The candidates", ""]
    for cand in ("C1", "C2", "C3"):
        if cand not in chosen:
            lines.append(f"- **{cand}: no cell qualifies on 2012-2021, dropped.**")
            continue
        name = chosen[cand][0]
        t = cells[name]
        chk = t[t["year"] > TUNE_END]
        f = fcells[name]
        f = f[since[f["i"]] >= start]
        corr = gn.correlations(f.assign(net=f["net_slip"]), day)
        ok = [True, chk["net_slip"].mean() > 0, f["net_slip"].mean() > 0,
              all(v < MAX_CORR for v in corr.values())]  # fmt: skip
        verdict = (
            "passes 1-4: next, a registered test on untouched markets" if all(ok) else "dropped"
        )
        lines += [
            f"- **{cand}: chosen {name}.** Check {chk['net_slip'].mean():+.3f} "
            f"(t {t_stat(chk):+.2f}, {len(chk):,} trades); FxPro {f['net_slip'].mean():+.3f} "
            f"(t {t_stat(f):+.2f}, {len(f):,}); daily correlation with the five "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + f". Conditions 2-4: {'/'.join('yes' if x else 'no' for x in ok[1:])}. "
            f"**{verdict}.**",
        ]
    lines += ["", "By year, every cell (net R with slip):", "",
              "| Year | " + " | ".join(cells) + " |",
              "| --- |" + " --- |" * len(cells)]  # fmt: skip
    years = sorted(set().union(*[set(t["year"]) for t in cells.values()]))
    for y in years:
        row = []
        for t in cells.values():
            g = t[t["year"] == y]
            row.append(f"{g['net_slip'].mean():+.3f} ({len(g)})" if len(g) else "-")
        lines.append(f"| {y} | " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-c123")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
