"""Managing the five's trades by their path (``docs/strategies/MGMT_FAST.md``, stage 2,
registered 2026-11-12 before any outcome).

    python -m app research mgmt-fast --export <GOLD M1>

The five's frozen entries; BASE = M8 (``gold_lab.simulate``, reproduced exactly); F1-F3 give
trades that reach +1 R within the two bars after entry ("fast") more room; A1 trails every trade
on the 15m swing."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import markout as mk
from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "mgmt_fast_result.md"  # not mgmt_fast.md: MGMT_FAST.md on Windows
CELLS = ("BASE", "F1", "F2", "F3", "A1")
FAST_BARS = 2
TUNE_END = 2021


def signals(cx: gl.Ctx) -> list[pd.DataFrame]:
    """The five's frozen entries, as ``gold_night.day_strategies`` builds them."""
    lv = gc.levels(
        cx,
        "LVL4H",
        gc.day_levels(cx),
        ge.LVL_MULT * cx.atr4h,
        gc.WINDOWS[ge.LVL_WINDOW],
        ge.LVL_HORIZON,
        ge.LVL_CAP,
    )
    piv = gc.levels(
        cx, "PIVOT", gc.pivot_levels(cx), cx.atr1h, gc.WINDOWS[ge.PIV_WINDOW], ge.PIV_HORIZON, None
    )
    sh = [
        gc.levels(
            cx,
            k,
            lvs,
            ge.LVL_MULT * cx.atr4h,
            gc.WINDOWS[ge.LVL_WINDOW],
            ge.LVL_HORIZON,
            ge.LVL_CAP,
        )
        for k, lvs in gs.shadow_levels(cx).items()
    ]
    return [lv, piv, *sh]  # one frame each: their own sort order decides same-bar ties, as now


def swings_15m(cx: gl.Ctx, f15: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The last confirmed 15m swing low and high and ATR(14, 15m), as known at each 5m bar."""
    lo, h = f15["low"].to_numpy(), f15["high"].to_numpy()
    swl, swh = gl.swing_lows(lo), -gl.swing_lows(-h)
    atr = gl.wilder(h, lo, f15["close"].to_numpy())
    return (gl.on_5m(cx.m, f15, swl), gl.on_5m(cx.m, f15, swh), gl.on_5m(cx.m, f15, atr))


def simulate(sig: pd.DataFrame, cx: gl.Ctx, cell: str, sw15: tuple) -> pd.DataFrame:
    """``gold_lab.simulate(..., "M8")`` with the cell's changes for fast (or all) trades."""
    h, lo, c = cx.h, cx.lo, cx.c
    swl, swh = gl.swing_lows(lo), -gl.swing_lows(-h)
    l15, h15, a15 = sw15
    out = []
    for name, g in sig.sort_values("i").groupby("strategy", sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            i, end = int(r.i), int(r.end)
            if i <= busy:
                continue
            s, e, risk = float(r.dir), float(r.entry), float(r.risk)
            cost = cx.spread[i] + gl.COMMISSION
            sl = e - s * risk
            armed, fast, decided = False, False, False
            exit_px, why, j = c[end], "time", end
            for j in range(i + 1, end + 1):
                hit_sl = lo[j] <= sl if s > 0 else h[j] >= sl
                if hit_sl:
                    exit_px, why = sl, "sl"
                    break
                best = h[j] - e if s > 0 else e - lo[j]
                if not decided and best >= risk:
                    decided, fast = True, j <= i + FAST_BARS
                wide = (cell in ("F2", "F3") and fast) or cell == "A1"
                arm_at = 2 * risk if cell in ("F1", "F3") and fast else risk
                if not armed and best >= arm_at:
                    armed = True
                    sl = e + s * cost if s * (e + s * cost - sl) > 0 else sl
                if armed:
                    if wide:
                        sw = l15[j] - 0.1 * a15[j] if s > 0 else h15[j] + 0.1 * a15[j]
                    else:
                        sw = swl[j] - 0.1 * cx.atr5[j] if s > 0 else swh[j] + 0.1 * cx.atr5[j]
                    if np.isfinite(sw) and s * (sw - sl) > 0 and s * (c[j] - sw) > 0:
                        sl = sw
            else:
                j = end
            busy = j
            out.append((name, i, j, s, risk, s * (exit_px - e) / risk, cost / risk, why, fast))
    cols = ["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit", "fast"]
    return gs.finish(pd.DataFrame(out, columns=cols), cx)


def diff_t(cx: gl.Ctx, a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, float]:
    m = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]")
    start = np.datetime64("2011-09-01T00:00", "m")

    def blk(t):
        return ((m[t["i"].to_numpy()] - start).astype("int64") // mk.BLOCK_MIN).astype(int)

    ba, bb = blk(a), blk(b)
    off = min(ba.min(), bb.min())
    idx = mk.resamples(int(max(ba.max(), bb.max()) - off) + 1)
    return mk.boot_t(idx, ba - off, a["net_slip"].to_numpy(), bb - off, b["net_slip"].to_numpy())


def portfolio(t: pd.DataFrame) -> tuple[float, float]:
    o = t.sort_values(["j", "i"], kind="stable")
    cum = o["net_slip"].cumsum().to_numpy()
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, cum])[1:] - cum)) if len(cum) else 0.0
    return float(cum[-1]) if len(cum) else 0.0, dd


def run_feed(fr: dict[str, pd.DataFrame], since: pd.Timestamp | None = None) -> tuple:
    cx = gl.context(fr)
    sigs = signals(cx)
    if since is not None:
        sigs = [
            x[pd.to_datetime(cx.m["close_utc"].to_numpy()[x["i"]], utc=True) >= since] for x in sigs
        ]
    sw15 = swings_15m(cx, fr["15m"])
    return cx, {
        c: pd.concat([simulate(x, cx, c, sw15) for x in sigs], ignore_index=True) for c in CELLS
    }


def section(cx, res: dict, name: str, rows: list[tuple[str, tuple[int, int]]]) -> list[str]:
    lines = [
        f"## {name}",
        "",
        "| Cell | Period | Trades | Fast | Mean net R | Minus BASE | t "
        "| Years better | Sum R | Largest drawdown R |",
        "|" + " --- |" * 10,
    ]
    for per, (a, b) in rows:
        base = res["BASE"][res["BASE"]["year"].between(a, b)]
        bmean = base["net_slip"].mean()
        byr = base.groupby("year")["net_slip"].mean()
        for c in CELLS:
            t = res[c][res[c]["year"].between(a, b)]
            dm, tt = diff_t(cx, t, base) if c != "BASE" else (0.0, np.nan)
            yr = t.groupby("year")["net_slip"].mean()
            better = (yr.reindex(byr.index) > byr).mean() if c != "BASE" else np.nan
            s, dd = portfolio(t)
            lines.append(
                f"| {c} | {per} | {len(t):,} | {t['fast'].mean():.0%} "
                f"| {t['net_slip'].mean():+.3f} | {t['net_slip'].mean() - bmean:+.3f} "
                f"| {tt:+.2f} | {better:.0%} | {s:+.1f} | {dd:.1f} |"
            )
    return lines + [""]


def build(export: Path) -> str:
    cx, res = run_feed(gl.load())
    tune = {c: t[t["year"] <= TUNE_END] for c, t in res.items()}
    base = tune["BASE"]
    byr = base.groupby("year")["net_slip"].mean()
    best, best_m, best_t = None, base["net_slip"].mean(), np.nan
    for c in CELLS[1:]:
        m = tune[c]["net_slip"].mean()
        _, tt = diff_t(cx, tune[c], base)
        yr = tune[c].groupby("year")["net_slip"].mean()
        better = (yr.reindex(byr.index) > byr).mean()
        if m > best_m and better >= 0.6 and tt >= 2:
            best, best_m, best_t = c, m, tt
    lines = [
        "# Managing the five's trades by their path (stage 2), XAUUSD and FxPro",
        "",
        "_`python -m app research mgmt-fast`, registered in `MGMT_FAST.md` (2026-11-12) "
        "before the run. Net R with slip; t of the difference from BASE (4-week block "
        "bootstrap)._",
        "",
    ]
    lines += section(
        cx, res, "XAUUSD", [("2012-2021", (2012, TUNE_END)), ("2022 to 2026-01-09", (2022, 2026))]
    )
    fcx, fres = run_feed(ge.frames_from_lines(gv.fx_lines(export)), gv.FX_START)
    lines += section(fcx, fres, "FxPro GOLD 2016-02 to 2026-11-05", [("all", (2016, 2026))])
    if best is None:
        lines += [
            "**No cell beats BASE on 2012-2021 by the registered bar (condition 1): M8 stays.**"
        ]
    else:
        chk = res[best][res[best]["year"] > TUNE_END]["net_slip"].mean()
        chk_b = res["BASE"][res["BASE"]["year"] > TUNE_END]["net_slip"].mean()
        fx, fx_b = fres[best]["net_slip"].mean(), fres["BASE"]["net_slip"].mean()
        ok = [True, chk > chk_b, fx > fx_b]
        lines += [
            f"**Chosen {best}** (2012-2021 {best_m:+.3f} R, t {best_t:+.2f} vs BASE). Check "
            f"{chk:+.3f} vs {chk_b:+.3f}; FxPro {fx:+.3f} vs {fx_b:+.3f}. Conditions 1-3: "
            f"{'/'.join('yes' if x else 'no' for x in ok)}. **"
            f"{'passes: propose an EA version to Fadi' if all(ok) else 'M8 stays'}.**"
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research mgmt-fast")
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
