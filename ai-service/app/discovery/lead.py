"""Lead test: does a round-number break continue on markets never read for it?
(``docs/discovery/LEAD_GRID.md``, registered 2026-11-11 before the run.)

    python -m app discovery lead --nas <NAS100 M1 export>

Gold's F5p BREAK rule on the five FX pairs (research store, to 2026-01-09) and NAS100 (FxPro
export without its summary bars), two grids each, h = 120 and 240 minutes; markouts in ATR(14, 1h)
units (the existence test against E0 and a moved-grid placebo) and in cost units (size)."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.config import instruments, splits
from app.data import clock
from app.data.importer import DEFAULT_OUT as STORE
from app.data.importer import M1
from app.data.mt5 import parse_export
from app.discovery import events as ev
from app.discovery import markout as mk
from app.research import five_nas as fn
from app.research import gold_ah as ah
from app.research import gold_lab as gl

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "discovery" / "lead_grid_result.md"
FX = {"EURUSD": (0.005, 0.01), "GBPUSD": (0.005, 0.01), "AUDUSD": (0.005, 0.01),
      "USDCAD": (0.005, 0.01), "USDJPY": (0.5, 1.0)}  # fmt: skip
NAS_GRIDS, GOLD_GRIDS = (100.0, 500.0), (50.0, 100.0)
H = (120, 240)
FX_COMMISSION, NAS_COMMISSION = 7e-5, 3.0
LOCKBOX = pd.Timestamp("2026-01-10", tz="UTC")
NAS_START = pd.Timestamp("2016-02-01", tz="UTC")
GOLD_REF = (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC"))
WARM = pd.Timedelta(days=30)
ALPHA = 0.05


# --- data -----------------------------------------------------------------------------------------


def load_fx(sym: str) -> pd.DataFrame:
    m = pd.read_parquet(STORE / sym / "m1.parquet", filters=[("ts_utc", "<", LOCKBOX)])
    return m.sort_values("ts_utc").reset_index(drop=True)


def load_nas(export: Path) -> pd.DataFrame:
    """NAS100 M1 bars as ``gold_exam.frames_from_lines`` builds them, before aggregation."""
    s = splits()
    inst = instruments()[gl.SYM]
    parsed = parse_export(fn.lines(export), inst, M1, s.server_tz)
    segments = clock.detect(parsed.bars, inst, s.server_tz)
    m1 = clock.apply(parsed.bars, segments)
    segments = clock.check_mismatch_weeks(m1, segments, s.server_tz)
    return clock.apply_mismatch_weeks(m1, segments, s.server_tz).reset_index(drop=True)


def bars_with(m1: pd.DataFrame, commission: np.ndarray | float) -> mk.Bars:
    """``markout.bars`` with the market's own commission in the cost unit."""
    bx = mk.bars(m1)
    bx.cost = m1["spread"].to_numpy() + commission
    return bx


# --- events ---------------------------------------------------------------------------------------


def grid_breaks(m1: pd.DataFrame, grids: tuple[float, ...],
                offsets: dict[float, float] | None = None) -> pd.DataFrame:  # fmt: skip
    """``events.f5``'s BREAK rule on any grid: an M1 close at or across the first level above
    (below) the previous close; sign = the cross; a level once per 60 minutes."""
    c = m1["close"].to_numpy()
    prev = np.r_[np.nan, c[:-1]]
    mins = ev.minutes(m1["ts_utc"])
    out = []
    for g in grids:
        off = (offsets or {}).get(g, 0.0)
        up_l = np.floor((prev - off) / g) * g + g + off
        dn_l = np.ceil((prev - off) / g) * g - g + off
        up, dn = c >= up_l, c <= dn_l
        sign = np.where(up, 1, np.where(dn, -1, 0))
        lvl = np.where(up, up_l, dn_l)
        idx = np.flatnonzero((sign != 0) & np.isfinite(prev))
        key = pd.DataFrame({"i": idx, "lvl": np.round(lvl[idx] / g, 6), "m": mins[idx]})
        keep = np.zeros(len(key), bool)
        for _, grp in key.groupby("lvl", sort=False):
            k_ = ev.refractory(grp["i"].to_numpy(), grp["m"].to_numpy())
            keep[grp.index.to_numpy()[k_]] = True
        out.append(ev._frame("LEAD", f"BREAK-{g:g}", idx[keep], sign[idx[keep]]))
    return pd.concat(out, ignore_index=True).sort_values("i", kind="stable").reset_index(drop=True)


def placebo(m1: pd.DataFrame, grids: tuple[float, ...]) -> pd.DataFrame:
    rng = np.random.default_rng(mk.SEED_PLACEBO)
    parts = []
    for _ in range(mk.GRID_DRAWS):
        parts.append(grid_breaks(m1, grids, {g: float(rng.uniform(0.1, 0.9)) * g for g in grids}))
    return pd.concat(parts, ignore_index=True)


# --- measurement ----------------------------------------------------------------------------------


def e0_atr(bx: mk.Bars, draws: np.ndarray, sign: np.ndarray, h: int) -> np.ndarray:
    flat = draws.ravel()
    s = np.repeat(sign, draws.shape[1]).astype(float)
    x = np.full(len(flat), np.nan)
    ok = flat >= 0
    x[ok] = mk.atr_markout(bx, flat[ok], s[ok], h)
    x = x.reshape(draws.shape)
    n = np.isfinite(x).sum(axis=1)
    return np.where(n > 0, np.where(np.isfinite(x), x, 0.0).sum(axis=1) / np.maximum(n, 1), np.nan)


def measure_market(name: str, m1: pd.DataFrame, grids: tuple[float, ...], commission,
                   start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:  # fmt: skip
    bx = bars_with(m1, commission)
    t = m1["ts_utc"]
    inside = ((t >= start) & (t < end)).to_numpy()
    ev_all = grid_breaks(m1, grids)
    pl_all = placebo(m1, grids)
    ev_all = ev_all[inside[ev_all["i"].to_numpy()]]
    pl_all = pl_all[inside[pl_all["i"].to_numpy()]]
    s_min = int(ev.minutes(pd.Series([start]))[0])
    e_min = int(ev.minutes(pd.Series([end]))[0])
    idx = mk.resamples(int((e_min - s_min) // mk.BLOCK_MIN) + 1)
    rng = np.random.default_rng(mk.SEED_E0)
    rows = []
    for g in grids:
        cell = f"BREAK-{g:g}"
        e = ev_all[ev_all["cell"] == cell]
        p = pl_all[pl_all["cell"] == cell]
        i, s = e["i"].to_numpy(), e["sign"].to_numpy().astype(float)
        pi, ps = p["i"].to_numpy(), p["sign"].to_numpy().astype(float)
        draws = mk.e0_draws(bx, i, rng)
        blk, pblk = mk.block_ids(bx.mins[i], s_min), mk.block_ids(bx.mins[pi], s_min)
        for h in H:
            a = mk.atr_markout(bx, i, s, h)
            d = a - e0_atr(bx, draws, s, h)
            ap = mk.atr_markout(bx, pi, ps, h)
            ex0, t0 = mk.boot_t(idx, blk, d)
            exp_, tp = mk.boot_t(idx, blk, a, pblk, ap)
            z = mk.z_markout(bx, i, s, h)
            rows.append({"market": name, "grid": g, "h": h, "n": int(np.isfinite(a).sum()),
                         "n_pl": int(np.isfinite(ap).sum()), "atr": np.nanmean(a), "ex_e0": ex0,
                         "t_e0": t0, "ex_pl": exp_, "t_pl": tp, "mean_z": np.nanmean(z),
                         "median_z": np.nanmedian(z)})  # fmt: skip
    return rows


def decide(r: pd.DataFrame) -> pd.DataFrame:
    r = r.copy()
    pos = (r["ex_e0"] > 0) & (r["ex_pl"] > 0)
    p = np.maximum(norm.sf(r["t_e0"].to_numpy()), norm.sf(r["t_pl"].to_numpy()))
    r["p"] = np.where(pos & np.isfinite(p), p, 1.0)
    r["holm"] = mk.holm(r["p"].to_numpy(), ALPHA)
    r["continues"] = r["holm"] & pos
    r["tradable"] = r["continues"] & (r["mean_z"] >= 2)
    return r


# --- report ---------------------------------------------------------------------------------------


def report(r: pd.DataFrame, gold: pd.DataFrame) -> str:
    markets = sorted(r.loc[r["continues"], "market"].unique())
    general = len(markets) >= 2
    lines = [
        "# Lead test: round-number breaks on untouched markets",
        "",
        "_`python -m app discovery lead`, registered in `LEAD_GRID.md` (2026-11-11) before the "
        "run. Markouts in ATR(14, 1h) units against E0 and a moved-grid placebo (4-week block "
        "bootstrap, B = 20,000); z = markout / (spread + commission)._",
        "",
        f"**Cells showing continuation (Holm over {len(r)} at 5%): {int(r['continues'].sum())}, "
        f"in {len(markets)} market(s){': ' + ', '.join(markets) if markets else ''}. "
        f"The lead {'generalises' if general else 'does not generalise'} (needs 2 of 6 markets)"
        f"{'; tradable cells: ' + str(int(r['tradable'].sum())) if general else ''}.**",
        "",
        "| Market | Grid | h | n | ATR markout | excess vs E0 (t) | vs placebo (t) | mean z "
        "| median z | Holm | continues |",
        "|" + " --- |" * 11,
    ]
    for x in r.itertuples():
        lines.append(
            f"| {x.market} | {x.grid:g} | {x.h} | {x.n:,} | {x.atr:+.3f} | {x.ex_e0:+.3f} "
            f"({x.t_e0:+.1f}) | {x.ex_pl:+.3f} ({x.t_pl:+.1f}) | {x.mean_z:+.2f} "
            f"| {x.median_z:+.2f} | {'yes' if x.holm else ''} | {'yes' if x.continues else ''} |"
        )
    lines += ["", "Reference, decides nothing: gold 2018-2021 (seen), the same code.", "",
              "| Grid | h | n | ATR markout | excess vs E0 (t) | vs placebo (t) | mean z |",
              "|" + " --- |" * 7]  # fmt: skip
    for x in gold.itertuples():
        lines.append(f"| {x.grid:g} | {x.h} | {x.n:,} | {x.atr:+.3f} | {x.ex_e0:+.3f} "
                     f"({x.t_e0:+.1f}) | {x.ex_pl:+.3f} ({x.t_pl:+.1f}) "
                     f"| {x.mean_z:+.2f} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    warnings.simplefilter("ignore", RuntimeWarning)
    ap = argparse.ArgumentParser(prog="python -m app discovery lead")
    ap.add_argument("--nas", type=Path, required=True, help="NAS100 M1 export")
    args = ap.parse_args(argv)
    rows = []
    for sym, grids in FX.items():
        m1 = load_fx(sym)
        start = m1["ts_utc"].iloc[0] + WARM
        rows += measure_market(sym, m1, grids, FX_COMMISSION * m1["close"].to_numpy(), start,
                               LOCKBOX)  # fmt: skip
        print(f"{sym}: done")
    nas = load_nas(args.nas)
    end = nas["ts_utc"].iloc[-1] + pd.Timedelta(minutes=1)
    rows += measure_market("NAS100", nas, NAS_GRIDS, NAS_COMMISSION, NAS_START, end)
    print("NAS100: done")
    r = decide(pd.DataFrame(rows))
    gold = ah.load_store()
    g = pd.DataFrame(measure_market("XAUUSD", gold, GOLD_GRIDS, ev.COMMISSION, *GOLD_REF))
    REPORT.write_text(report(r, g), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
