"""The five as a portfolio: risk split across same-direction trades
(``docs/portfolio/RISK_SPLIT.md``, registered 2026-11-12).

    python -m app research risk-split --export <GOLD M1 export>

Same trades as the EA (``gold_live.five_trades``); only the weight w changes: BASE 1, SPLIT
1 / (1 + k), LEARNED 1 / (1 + k x rho), k = the five's trades open in the same direction at the
entry, rho from the store 2012-2021. Daily Sharpe difference on the store 2022 to 2026-01-09
(4-week block bootstrap, Holm), max drawdown at equal return, FxPro 2016-02 to 2026-11-05."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import decide as dc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.scoring.volatility import W_FROM, at_ny

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "portfolio" / "risk_split_result.md"  # not RISK_SPLIT.md (Windows case)
DEFAULT_EXPORT = Path("D:/GOLD_M1_201501020000_202611052359.csv")
FIVE = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
SIX = (*FIVE, "ROUND")
RULES = ("BASE", "SPLIT", "LEARNED")
STORE_FROM = pd.Timestamp("2012-01-01", tz="UTC")
RHO_TO, TEST_FROM, TEST_TO = 20211231, 20220101, 20260109
FX_TO = 20261105
BOOT, SEED = 10_000, 20261115
HEAD = "| Data | Rule | Days | Mean R a day | Total R | Daily Sharpe | Max DD at equal return (R) |"


# --- weights -------------------------------------------------------------------------------------


def open_same(t: pd.DataFrame, names: tuple[str, ...]) -> pd.DataFrame:
    """For each trade of ``names``: k and the index labels of the same-direction trades open at
    its entry (entered earlier, or at the same bar earlier in ``names`` order; exit bar >= i)."""
    s = t[t["strategy"].isin(names)].copy()
    s["order"] = s["strategy"].map({n: k for k, n in enumerate(names)})
    s = s.sort_values(["i", "order"], kind="stable")
    rows, ks, partners = [], [], []
    for _, g in s.groupby("ny_day", sort=False):
        idx, i, j, d = (
            g.index.to_numpy(),
            g["i"].to_numpy(),
            g["j"].to_numpy(),
            g["dir"].to_numpy(),
        )
        for n in range(len(g)):
            m = np.arange(n)
            hit = m[(d[m] == d[n]) & (j[m] >= i[n])]
            rows.append(idx[n])
            ks.append(len(hit))
            partners.append(idx[hit].tolist())
    return pd.DataFrame({"k": ks, "partners": partners}, index=pd.Index(rows))


def rho_of(t: pd.DataFrame, o: pd.DataFrame) -> tuple[float, int, pd.DataFrame]:
    """Pooled correlation of net R with slip over (new trade, open same-direction trade) pairs;
    also per strategy pair."""
    a, b = [], []
    for n, ps in o["partners"].items():
        for m in ps:
            a.append(n)
            b.append(m)
    if len(a) < 3:
        return 0.0, len(a), pd.DataFrame()
    x, y = t.loc[a, "net_slip"].to_numpy(), t.loc[b, "net_slip"].to_numpy()
    rho = float(np.corrcoef(x, y)[0, 1])
    pairs = pd.DataFrame(
        {
            "new": t.loc[a, "strategy"].to_numpy(),
            "open": t.loc[b, "strategy"].to_numpy(),
            "x": x,
            "y": y,
        }
    )
    by = pairs.groupby(["new", "open"]).apply(
        lambda g: pd.Series({"pairs": len(g), "rho": g["x"].corr(g["y"]) if len(g) > 2 else np.nan})
    )
    return rho, len(a), by


def weights(o: pd.DataFrame, rho: float) -> pd.DataFrame:
    k = o["k"].to_numpy()
    return pd.DataFrame(
        {"BASE": 1.0, "SPLIT": 1 / (1 + k), "LEARNED": 1 / (1 + k * rho)}, index=o.index
    )


# --- measures -------------------------------------------------------------------------------------


def day_table(t: pd.DataFrame, w: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame:
    """Day results (sum of w x net R with slip) per rule, days lo..hi with a BASE trade."""
    s = t.loc[w.index]
    s = s[(s["ny_day"] >= lo) & (s["ny_day"] <= hi)]
    return pd.DataFrame(
        {r: (w.loc[s.index, r] * s["net_slip"]).groupby(s["ny_day"]).sum() for r in RULES}
    ).sort_index()


def sharpe(x: np.ndarray) -> float:
    return float(np.mean(x) / np.std(x, ddof=1))


def max_dd(x: np.ndarray) -> float:
    c = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(np.r_[0.0, c])[1:] - c))


def dd_equal(d: pd.DataFrame, rule: str) -> float:
    m = d[rule].mean()
    if m <= 0:
        return np.nan
    return max_dd(d[rule].to_numpy() * d["BASE"].mean() / m)


def blocks_of(days: pd.Index) -> np.ndarray:
    ts = pd.to_datetime(pd.Index(days).astype(str), format="%Y%m%d")
    return dc.block_ids(at_ny(ts, W_FROM))


def boot(d: pd.DataFrame) -> dict[str, dict]:
    """Sharpe(rule) - Sharpe(BASE) under a 4-week block bootstrap of days (same draws)."""
    ids, inv = np.unique(blocks_of(d.index), return_inverse=True)
    k = len(ids)
    n = np.bincount(inv, minlength=k).astype(float)
    s1 = {r: np.bincount(inv, d[r].to_numpy(), k) for r in RULES}
    s2 = {r: np.bincount(inv, d[r].to_numpy() ** 2, k) for r in RULES}
    draws = np.random.default_rng(SEED).integers(0, k, size=(BOOT, k))
    nn = n[draws].sum(axis=1)

    def sh(r):
        a, b = s1[r][draws].sum(axis=1), s2[r][draws].sum(axis=1)
        mean = a / nn
        return mean / np.sqrt((b - nn * mean**2) / (nn - 1))

    base = sh("BASE")
    out = {}
    for r in ("SPLIT", "LEARNED"):
        star = sh(r) - base
        out[r] = {
            "diff": sharpe(d[r].to_numpy()) - sharpe(d["BASE"].to_numpy()),
            "lo": float(np.percentile(star, 2.5)),
            "hi": float(np.percentile(star, 97.5)),
            "p": float((1 + np.count_nonzero(star <= 0)) / (BOOT + 1)),
            "blocks": k,
        }
    p = {r: out[r]["p"] for r in out}
    first = min(p, key=p.get)
    out[first]["holm"] = min(1.0, 2 * p[first])
    other = next(r for r in p if r != first)
    out[other]["holm"] = max(out[first]["holm"], p[other])
    return out


def summary(d: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            r: {
                "days": len(d),
                "mean": d[r].mean(),
                "total": d[r].sum(),
                "sharpe": sharpe(d[r].to_numpy()),
                "dd_eq": dd_equal(d, r),
            }
            for r in RULES
        }
    ).T


# --- data ----------------------------------------------------------------------------------


def trades(fr: dict[str, pd.DataFrame], start: pd.Timestamp) -> pd.DataFrame:
    _, every, _, cx = gv.five_trades(fr, start=start, with_round=True)
    every = every.copy()
    every["ny_day"] = cx.ny_day[every["i"].to_numpy()]
    return every.reset_index(drop=True)


def side(t: pd.DataFrame, rho: float | None = None) -> dict:
    o5 = open_same(t, FIVE)
    if rho is None:
        fit = o5[t.loc[o5.index, "ny_day"] <= RHO_TO]
        r, npairs, by = rho_of(t, fit)
        rho = float(np.clip(r, 0.0, 1.0))
        extra = {"rho_raw": r, "pairs": npairs, "by": by}
    else:
        extra = {}
    o6 = open_same(t, SIX)
    return {
        "t": t,
        "o5": o5,
        "w5": weights(o5, rho),
        "o6": o6,
        "w6": weights(o6, rho),
        "rho": rho,
        **extra,
    }


# --- report ---------------------------------------------------------------------------------------


def fmt_summary(name: str, s: pd.DataFrame) -> list[str]:
    return [
        f"| {name} | {r} | {int(x['days']):,} | {x['mean']:+.4f} | {x['total']:+.1f} "
        f"| {x['sharpe']:.4f} | {x['dd_eq']:.1f} |"
        for r, x in s.iterrows()
    ]


def episodes(d: pd.DataFrame, top: int = 3) -> list[tuple[int, int, float]]:
    """The deepest BASE drawdowns: (peak day, trough day, depth), non-overlapping."""
    c = d["BASE"].cumsum()
    out, used = [], np.zeros(len(c), bool)
    vals = c.to_numpy()
    for _ in range(top):
        peak = np.maximum.accumulate(np.where(used, -np.inf, vals))
        dd = np.where(used, -np.inf, peak - vals)
        e = int(np.argmax(dd))
        if not np.isfinite(dd[e]) or dd[e] <= 0:
            break
        s = int(np.flatnonzero((vals[: e + 1] == peak[e]) & ~used[: e + 1])[-1])
        out.append((int(c.index[s]), int(c.index[e]), float(dd[e])))
        used[s : e + 1] = True
    return out


def report(st: dict, fx: dict) -> str:
    t = st["t"]
    test = day_table(t, st["w5"], TEST_FROM, TEST_TO)
    early = day_table(t, st["w5"], 20120101, RHO_TO)
    fxd = day_table(fx["t"], fx["w5"], 0, FX_TO)
    b = boot(test)
    s_test, s_fx = summary(test), summary(fxd)
    passed = {}
    for r in ("SPLIT", "LEARNED"):
        passed[r] = (
            b[r]["diff"] > 0
            and b[r]["holm"] < 0.05
            and s_test.loc[r, "dd_eq"] < s_test.loc["BASE", "dd_eq"]
            and s_fx.loc[r, "dd_eq"] < s_fx.loc["BASE", "dd_eq"]
            and s_fx.loc[r, "sharpe"] > s_fx.loc["BASE", "sharpe"]
        )
    win = [r for r in passed if passed[r]]
    choice = max(win, key=lambda r: s_test.loc[r, "sharpe"]) if win else None
    lines = [
        "# The five as a portfolio: risk split, result",
        "",
        "_`python -m app research risk-split`, registered in `RISK_SPLIT.md`. Same trades as the "
        "EA; only the weight changes. Day result = sum of w x net R with slip. Sharpe per day over "
        f"days with a trade of the five. 4-week block bootstrap, {BOOT:,} resamples, seed {SEED}._",
        "",
        f"rho (store 2012-2021, {st['pairs']:,} pairs): {st['rho_raw']:+.4f}, used "
        f"{st['rho']:.4f}.",
        "",
        "## Decision",
        "",
    ]
    if choice:
        lines.append(
            f"**{', '.join(win)} pass{'es' if len(win) == 1 else ''}; {choice} is "
            "chosen.** Using it live needs the EA step of `RISK_SPLIT.md` §7."
        )
    else:
        lines.append("**No rule passes. The EA keeps equal risk.**")
    lines += [
        "",
        "| Rule | Sharpe diff (store 2022 to 2026-01-09) | 95% | p | Holm p | DD at equal return "
        "smaller (store / FxPro) | FxPro Sharpe higher | Passes |",
        "|" + " --- |" * 8,
    ]
    for r in ("SPLIT", "LEARNED"):
        x = b[r]
        lines.append(
            f"| {r} | {x['diff']:+.4f} | {x['lo']:+.4f} to {x['hi']:+.4f} | {x['p']:.4f} "
            f"| {x['holm']:.4f} | "
            f"{'yes' if s_test.loc[r, 'dd_eq'] < s_test.loc['BASE', 'dd_eq'] else 'no'} / "
            f"{'yes' if s_fx.loc[r, 'dd_eq'] < s_fx.loc['BASE', 'dd_eq'] else 'no'} | "
            f"{'yes' if s_fx.loc[r, 'sharpe'] > s_fx.loc['BASE', 'sharpe'] else 'no'} "
            f"| {'yes' if passed[r] else 'no'} |"
        )
    lines += [
        "",
        "## Each rule",
        "",
        HEAD,
        "|" + " --- |" * 7,
        *fmt_summary("Store 2022 to 2026-01-09 (test)", s_test),
        *fmt_summary("Store 2012-2021 (rho fitted here)", summary(early)),
        *fmt_summary("FxPro 2016-02 to 2026-11-05", s_fx),
        *fmt_summary("FxPro 2026-01-12 on (never used)", summary(fxd[fxd.index >= 20260112])),
        "",
        "## Same-direction overlap (BASE trades of the five)",
        "",
        "| Data | k | Trades | Share | Mean net R with slip |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, s in (("Store 2012 to 2026-01-09", st), ("FxPro", fx)):
        g = s["t"].loc[s["o5"].index].assign(k=s["o5"]["k"].clip(upper=3))
        for k, x in g.groupby("k"):
            lines.append(
                f"| {name} | {k}{'+' if k == 3 else ''} | {len(x):,} "
                f"| {len(x) / len(g):.1%} | {x['net_slip'].mean():+.4f} |"
            )
    by = st["by"].dropna()
    lines += [
        "",
        "## rho per strategy pair (store 2012-2021; new trade x open trade)",
        "",
        "| New | Open | Pairs | rho |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {a} | {o} | {int(x['pairs'])} | {x['rho']:+.3f} |" for (a, o), x in by.iterrows()]
    lines += [
        "",
        "(The registration asked for rho by level family; it is given per strategy pair, "
        "which is what the trades carry.)",
        "",
        "## Per year (store; BASE / SPLIT / LEARNED)",
        "",
        "| Year | Total R | Sharpe | Max DD at equal return |",
        "| --- | --- | --- | --- |",
    ]
    full = day_table(t, st["w5"], 20120101, TEST_TO)
    for y, g in full.groupby(full.index // 10000):
        s = summary(g)
        lines.append(
            "| "
            + str(y)
            + " | "
            + " / ".join(f"{s.loc[r, 'total']:+.1f}" for r in RULES)
            + " | "
            + " / ".join(f"{s.loc[r, 'sharpe']:.3f}" for r in RULES)
            + " | "
            + " / ".join(f"{s.loc[r, 'dd_eq']:.1f}" for r in RULES)
            + " |"
        )
    lines += [
        "",
        "## The six with ROUND (reported, not tested)",
        "",
        HEAD,
        "|" + " --- |" * 7,
    ]
    lines += fmt_summary(
        "Store 2022 to 2026-01-09", summary(day_table(t, st["w6"], TEST_FROM, TEST_TO))
    )
    lines += fmt_summary(
        "FxPro 2016-02 to 2026-11-05", summary(day_table(fx["t"], fx["w6"], 0, FX_TO))
    )
    lines += [
        "",
        "## The deepest BASE drawdowns (FxPro) and each rule in them",
        "",
        "| Peak day | Trough day | BASE fall (R) | SPLIT change | LEARNED change |",
        "| --- | --- | --- | --- | --- |",
    ]
    for a, z, depth in episodes(fxd):
        g = fxd[(fxd.index > a) & (fxd.index <= z)]
        sc = {
            r: fxd["BASE"].mean() / fxd[r].mean() if fxd[r].mean() > 0 else np.nan
            for r in ("SPLIT", "LEARNED")
        }
        lines.append(
            f"| {a} | {z} | {-depth:+.1f} | {g['SPLIT'].sum() * sc['SPLIT']:+.1f} "
            f"| {g['LEARNED'].sum() * sc['LEARNED']:+.1f} |"
        )
    lines += ["", "Rule changes are scaled to BASE's mean (equal return).", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="risk-split")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    a = ap.parse_args(argv or [])
    st = side(trades(gl.load(), STORE_FROM))
    fx_fr = ge.frames_from_lines(gv.fx_lines(a.export))
    fx = side(trades(fx_fr, gv.FX_START), rho=st["rho"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report(st, fx), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
