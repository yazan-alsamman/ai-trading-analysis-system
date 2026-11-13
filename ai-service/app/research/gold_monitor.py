"""The live monitor of the five and ROUND (``docs/strategies/GOLD_MONITOR.md``, registered
2026-11-13).

    python -m app research gold-demo reference --export <GOLD M1 export from 2016>   # once
    python -m app research gold-demo check --report <report> [--export <GOLD M1>]     # weekly

``reference`` runs the six on FxPro 2016-02 to 2026-11-05, refuses if a pool's mean differs from
the registered table by more than 0.002 R, chooses the CUSUM threshold h by simulation and stores
both (``gold_monitor_reference.parquet`` / ``.json``). ``health`` turns the demo's trades into the
four layers (A process, B edge estimate, C CUSUM, D drawdown) and a status."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv

STRATEGIES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL", "ROUND")
REF_FILE = gl.STORE / "gold_monitor_reference.parquet"
REF_META = gl.STORE / "gold_monitor_reference.json"
REF_LAST_DAY = 20261105
REF = {  # GOLD_MONITOR.md §2: trades, mean, SD of net R with slip
    "LVL4H": (1141, 0.082, 1.18),
    "PIVOT": (2116, -0.019, 1.36),
    "PIVW": (994, 0.025, 1.13),
    "ASIA": (1695, 0.041, 1.17),
    "PWHL": (496, 0.106, 1.17),
    "ROUND": (794, 0.132, 1.16),
    "ALL6": (7236, 0.042, 1.22),
}
TOL = 0.002
# A
MATCH_MIN, SLIP_R, COST_R, LAST_N, WEEK_EXPECTED = 0.90, 0.05, 0.03, 30, 22
# B
HAIRCUT, PRIOR_SD, RED_P, REVIEW_P = 0.5, 0.10, 0.10, 0.05
# C
GOOD, BAD, SD = 0.042, -0.058, 1.22
H_STEP, ARL0_MIN, CUSUM_PATHS, CUSUM_CAP, CUSUM_SEED = 0.25, 2000, 2000, 20_000, 20261117
# D
DD_PATHS, DD_SEED, DD_AMBER, DD_RED = 10_000, 20261118, 0.95, 0.99


# --- the reference ----------------------------------------------------------------------------


def pools(t: pd.DataFrame) -> dict[str, np.ndarray]:
    out = {s: t.loc[t["strategy"] == s, "net"].to_numpy() for s in STRATEGIES}
    out["ALL6"] = t["net"].to_numpy()
    return out


def verify(t: pd.DataFrame) -> None:
    for name, x in pools(t).items():
        n, m, _ = REF[name]
        if len(x) != n or abs(x.mean() - m) > TOL:
            raise SystemExit(
                f"reference {name}: {len(x)} trades, mean {x.mean():+.4f}; "
                f"registered {n}, {m:+.3f}: refused"
            )


def week_of(ny_day: pd.Series) -> np.ndarray:
    d = pd.to_datetime(ny_day.astype(str), format="%Y%m%d")
    monday = d - pd.to_timedelta(d.dt.day_of_week, unit="D")
    return monday.dt.strftime("%Y%m%d").astype(int).to_numpy()


def weeks(t: pd.DataFrame) -> list[np.ndarray]:
    """The reference ALL6 trades by calendar week, in time order."""
    t = t.sort_values(["ny_day", "i"], kind="stable")
    return [g["net"].to_numpy() for _, g in t.groupby("week", sort=True)]


def paths(wk: list[np.ndarray], n: int, length: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` paths of ``length`` trades from whole weeks drawn with replacement."""
    mean_len = np.mean([len(w) for w in wk])
    k = int(np.ceil(length / mean_len * 1.5)) + 2
    out = np.empty((n, length))
    for p in range(n):
        x = np.concatenate([wk[i] for i in rng.integers(0, len(wk), k)])
        while len(x) < length:
            x = np.concatenate([x, *[wk[i] for i in rng.integers(0, len(wk), k)]])
        out[p] = x[:length]
    return out


def cusum(x: np.ndarray) -> np.ndarray:
    """S_t = max(0, S_{t-1} + z_t) from S_0 = 0, along the last axis (Lindley's closed form)."""
    z = ((BAD - GOOD) * x - (BAD**2 - GOOD**2) / 2) / SD**2
    c = np.cumsum(z, axis=-1)
    return c - np.minimum(np.minimum.accumulate(c, axis=-1), 0.0)


def first_cross(run_max: np.ndarray, h: float) -> np.ndarray:
    """Trades to the first S >= h on each path (the cap when never), from S's running maximum."""
    hit = run_max >= h
    return np.where(hit[:, -1], hit.argmax(axis=1) + 1, run_max.shape[1])


def choose_h(wk: list[np.ndarray], chunk: int = 100) -> dict:
    """The smallest multiple of 0.25 with an average run to a false alarm >= 2,000 trades
    (paths in chunks to keep memory small)."""
    grid = np.arange(1, 81) * H_STEP
    rng = np.random.default_rng(CUSUM_SEED)
    sum0, sum1 = np.zeros(len(grid)), np.zeros(len(grid))
    for _ in range(CUSUM_PATHS // chunk):
        x = paths(wk, chunk, CUSUM_CAP, rng)
        m0 = np.maximum.accumulate(cusum(x), axis=1)
        m1 = np.maximum.accumulate(cusum(x - 0.10), axis=1)
        for g, h in enumerate(grid):
            sum0[g] += first_cross(m0, h).sum()
            sum1[g] += first_cross(m1, h).sum()
    arl0, arl1 = sum0 / CUSUM_PATHS, sum1 / CUSUM_PATHS
    g = int(np.argmax(arl0 >= ARL0_MIN))
    if arl0[g] < ARL0_MIN:
        raise SystemExit("no h up to 20 reaches the registered false-alarm run")
    return {"h": float(grid[g]), "arl0": float(arl0[g]), "arl1": float(arl1[g]), "cap": CUSUM_CAP}


def build_reference(export: Path) -> dict:
    fr = ge.frames_from_lines(gv.fx_lines(export))
    _, every, _, cx = gv.five_trades(fr, with_round=True)
    every["ny_day"] = cx.ny_day[every["i"].to_numpy()]
    t = every[every["ny_day"] <= REF_LAST_DAY]
    t = pd.DataFrame(
        {"strategy": t["strategy"], "ny_day": t["ny_day"], "i": t["i"], "net": t["net_slip"]}
    ).reset_index(drop=True)
    verify(t)
    t["week"] = week_of(t["ny_day"])
    meta = {"export": export.name, "trades": len(t), **choose_h(weeks(t))}
    t.to_parquet(REF_FILE, index=False)
    REF_META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def load_reference() -> tuple[pd.DataFrame, dict] | None:
    if not (REF_FILE.exists() and REF_META.exists()):
        return None
    t = pd.read_parquet(REF_FILE)
    verify(t)
    return t, json.loads(REF_META.read_text(encoding="utf-8"))


# --- the four layers ---------------------------------------------------------------------------


def layer_a(demo: pd.DataFrame, matched: tuple[int, int, int] | None) -> list[dict]:
    """A1-A4: (check, value, flag). ``matched``: (both, demo only, Python only) or None."""
    out = []
    if matched is None:
        out.append({"check": "A1 match with Python", "value": "no export", "flag": "-"})
    else:
        both, d_only, p_only = matched
        sd = both / (both + d_only) if both + d_only else np.nan
        sp = both / (both + p_only) if both + p_only else np.nan
        red = (sd < MATCH_MIN) or (sp < MATCH_MIN)
        out.append(
            {
                "check": "A1 match with Python",
                "value": f"demo {sd:.0%}, Python {sp:.0%}",
                "flag": "red" if red else "ok",
            }
        )
    last = demo.tail(LAST_N)
    slip = float((last["slip"].fillna(0) / last["risk"]).mean()) if len(last) else np.nan
    out.append(
        {
            "check": f"A2 entry slippage, last {len(last)} (R)",
            "value": f"{slip:+.3f}",
            "flag": "amber" if slip > SLIP_R else "ok",
        }
    )
    cost = float((last["gross"] - last["net"]).mean()) if len(last) else np.nan
    out.append(
        {
            "check": f"A4 cost, last {len(last)} (R)",
            "value": f"{cost:+.3f}",
            "flag": "amber" if cost > COST_R else "ok",
        }
    )
    out.insert(2, week_check(demo))
    return out


def week_check(demo: pd.DataFrame) -> dict:
    """A3: trades in the last full calendar week (Monday-Sunday) before the latest trade's week."""
    name = "A3 trades in the last full week"
    if demo.empty:
        return {"check": name, "value": "no trades", "flag": "-"}
    day = demo["opened"].dt.normalize()
    monday = day - pd.to_timedelta(day.dt.day_of_week, unit="D")
    prev = monday.max() - pd.Timedelta(days=7)
    if monday.min() > prev:
        return {"check": name, "value": "no full week yet", "flag": "-"}
    n = int((monday == prev).sum())
    lo, hi = stats.poisson.ppf(0.005, WEEK_EXPECTED), stats.poisson.ppf(0.995, WEEK_EXPECTED)
    flag = "amber" if n < lo or n > hi else "ok"
    return {
        "check": name,
        "value": f"{n} (week of {prev:%Y-%m-%d}; expected 22, {int(lo)}-{int(hi)})",
        "flag": flag,
    }


def layer_b(demo: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for name, x in pools(demo).items():
        _, m_ref, sd = REF[name]
        m0, n = HAIRCUT * m_ref, len(x)
        prec = 1 / PRIOR_SD**2 + n / sd**2
        mean = (m0 / PRIOR_SD**2 + (x.sum() / sd**2 if n else 0.0)) / prec
        s = np.sqrt(1 / prec)
        p = float(stats.norm.cdf(mean / s))
        if name == "ALL6":
            flag = "red" if p < RED_P else "ok"
        else:
            flag = "review" if p < REVIEW_P else "ok"
        rows[name] = {
            "trades": n,
            "mean": float(x.mean()) if n else np.nan,
            "post": mean,
            "lo": mean - 1.645 * s,
            "hi": mean + 1.645 * s,
            "p": p,
            "flag": flag,
        }
    return pd.DataFrame(rows).T


def layer_c(demo: pd.DataFrame, h: float) -> dict:
    x = demo["net"].to_numpy()
    s = cusum(x) if len(x) else np.array([0.0])
    return {
        "s": float(s[-1]),
        "max": float(s.max()),
        "h": h,
        "flag": "red" if s.max() >= h else "ok",
    }


def drawdown_now(x: np.ndarray) -> np.ndarray:
    c = np.cumsum(x, axis=-1)
    peak = np.maximum.accumulate(
        np.concatenate([np.zeros(c.shape[:-1] + (1,)), c], axis=-1), axis=-1
    )[..., 1:]
    return (peak - c)[..., -1]


def layer_d(demo: pd.DataFrame, ref: pd.DataFrame) -> dict:
    x = demo["net"].to_numpy()
    if not len(x):
        return {"dd": 0.0, "pct": np.nan, "flag": "-"}
    dd = float(drawdown_now(x))
    sims = drawdown_now(paths(weeks(ref), DD_PATHS, len(x), np.random.default_rng(DD_SEED)))
    pct = float((sims < dd).mean())
    flag = "red" if pct > DD_RED else "amber" if pct > DD_AMBER else "ok"
    return {
        "dd": dd,
        "pct": pct,
        "flag": flag,
        "p95": float(np.quantile(sims, 0.95)),
        "p99": float(np.quantile(sims, 0.99)),
    }


# --- the section ------------------------------------------------------------------------------


def health(demo: pd.DataFrame, matched: tuple[int, int, int] | None) -> list[str]:
    head = ["## Health (`GOLD_MONITOR.md`)", ""]
    loaded = load_reference()
    if loaded is None:
        return head + [
            "The reference is missing: run `python -m app research gold-demo reference "
            "--export <GOLD M1 export from 2016>` once.",
            "",
        ]
    ref, meta = loaded
    demo = demo.sort_values("opened", kind="stable").reset_index(drop=True)
    a, b = layer_a(demo, matched), layer_b(demo)
    c, d = layer_c(demo, meta["h"]), layer_d(demo, ref)
    reds = [r["check"] for r in a if r["flag"] == "red"]
    reds += ["B edge (ALL6)"] * (b.loc["ALL6", "flag"] == "red")
    reds += ["C CUSUM"] * (c["flag"] == "red") + ["D drawdown"] * (d["flag"] == "red")
    ambers = [r["check"] for r in a if r["flag"] == "amber"] + ["D drawdown"] * (
        d["flag"] == "amber"
    )
    review = [k for k in STRATEGIES if b.loc[k, "flag"] == "review"]
    status = "RED" if reds else "AMBER" if ambers else "GREEN"
    lines = head + [
        f"**Status: {status}**"
        + (f" (red: {', '.join(reds)})" if reds else "")
        + (f" (amber: {', '.join(ambers)})" if ambers else "")
        + (f"; review: {', '.join(review)}" if review else "")
        + ".",
        "",
        "Red, process (A1): pause the EA until fixed. Red, edge (B, C, D): no move to real money "
        "on these rules; nothing is changed in reaction.",
        "",
        "### A. Process",
        "",
        "| Check | Value | Flag |",
        "| --- | --- | --- |",
        *[f"| {r['check']} | {r['value']} | {r['flag']} |" for r in a],
        "",
        "### B. Edge estimate (prior: half the reference mean, SD 0.10 R)",
        "",
        "| Pool | Demo trades | Demo mean | Estimate (90%) | P(edge > 0) | Flag |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for k, r in b.iterrows():
        dm = f"{r['mean']:+.3f}" if r["trades"] else "-"
        lines.append(
            f"| {k} | {int(r['trades'])} | {dm} | {r['post']:+.3f} ({r['lo']:+.3f} to "
            f"{r['hi']:+.3f}) | {r['p']:.0%} | {r['flag']} |"
        )
    lines += [
        "",
        "### C. CUSUM (ALL6; good +0.042, broken −0.058)",
        "",
        f"S now {c['s']:.2f}, highest {c['max']:.2f}, red at h = {c['h']:.2f} (false alarm on "
        f"average every {meta['arl0']:,.0f} trades; an edge 0.10 R worse found in about "
        f"{meta['arl1']:,.0f}). Flag: {c['flag']}.",
        "",
        "### D. Drawdown against history (ALL6)",
        "",
        (
            f"Current drawdown {d['dd']:.1f} R; worse than {d['pct']:.0%} of 10,000 historical "
            f"paths of the same length (95th: {d['p95']:.1f} R, 99th: {d['p99']:.1f} R). "
            f"Flag: {d['flag']}."
        )
        if d["flag"] != "-"
        else "No trades yet.",
        "",
    ]
    return lines
