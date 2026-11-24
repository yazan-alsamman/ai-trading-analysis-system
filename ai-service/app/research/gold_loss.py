"""Gold: what the five strategies' losing trades share (``docs/strategies/GOLD_LOSS.md``,
registered 2026-11-10; Fadi's idea).

    python -m app research gold-loss build --export <GOLD M1>

Every trade of the five (one at a time, M8) gets 16 features known at its entry bar. On 2012-2021
each bucket's mean net R is screened, and up to two buckets are removed greedily; the gain is
held against 50 shuffles of the net R. The filter is then read on the check and on FxPro."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_exit as gx
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_pbk as gp
from app.research import gold_shadow as gs
from app.research import gold_time as gt

REPORT = gl.OUT_DIR / "gold_loss_xauusd.md"  # not gold_loss.md: GOLD_LOSS.md on Windows
TUNE_END = gc.TUNE_END
SEED, SHUFFLES, MIN_SHARE, STEPS, MIN_KEEP = 20261110, 50, 0.05, 2, 0.6
QUANT = ["d_atr", "vol_regime", "moved", "prev_bar", "yday_range", "cost_q"]


def trades(cx: gl.Ctx) -> pd.DataFrame:
    sig = gx.signals(cx)
    t = gs.finish(gl.simulate(sig, cx, "M8"), cx)
    keep = sig.drop(columns=["dir", "risk"]).drop_duplicates(["strategy", "i"])
    t = t.merge(keep, on=["strategy", "i"], how="left")
    return gn.with_day(t, cx).sort_values(["i", "strategy"], kind="stable").reset_index(drop=True)


def features(cx: gl.Ctx, fr: dict[str, pd.DataFrame], t: pd.DataFrame) -> pd.DataFrame:
    """Raw features of each trade, all known at its entry bar (quantile ones still numeric)."""
    i = t["i"].to_numpy()
    d = t["dir"].to_numpy()
    ny = cx.ny_min[i]
    hour = np.select([ny < 300, ny < 480, ny < 600, ny < 720], ["02-05", "05-08", "08-10", "10-12"],
                     "12-16")  # fmt: skip
    news = ((ny >= 505) & (ny < 515)) | ((ny >= 595) & (ny < 605))
    market = t["entry"].to_numpy() != t["level"].to_numpy()
    d1 = cx.d1
    atr_d1 = pd.Series(gl.wilder(*(d1[k].to_numpy() for k in ("high", "low", "close"))))
    regime = atr_d1.rolling(250).rank(pct=True).shift(1).to_numpy()
    yday = (d1["high"] - d1["low"]).shift(1).to_numpy()
    day = np.maximum(cx.day_idx[i], 0)
    first = gt.Clock(cx).first
    open_ = cx.o[np.maximum(first[day], 0)]
    e = t["entry"].to_numpy()
    tr1, tr4 = gp.trends(cx, fr)
    struct = np.where((tr1[i] == d) & (tr4[i] == d), "with",
                      np.where((tr1[i] == -d) & (tr4[i] == -d), "against", "mixed"))  # fmt: skip
    earlier = t.groupby("tday").cumcount().to_numpy()  # trades sorted by entry bar
    return pd.DataFrame({
        "strategy": t["strategy"].to_numpy(), "kind": t["kind"].to_numpy(),
        "side": np.where(d > 0, "buy", "sell"), "hour": hour,
        "weekday": cx.weekday[i].astype(str), "news": np.where(news, "yes", "no"),
        "fill": np.where(market, "market", "stop"),
        "d_atr": t["risk"].to_numpy() / cx.atrd[i], "vol_regime": regime[day],
        "moved": np.abs(e - open_) / cx.atrd[i],
        "with_day": np.where(np.sign(e - open_) == d, "with", "against"),
        "structure": struct,
        "prev_bar": (cx.h[i - 1] - cx.lo[i - 1]) / cx.atr5[i - 1],
        "yday_range": yday[day] / cx.atrd[i],
        "earlier": np.minimum(earlier, 2).astype(str),
        "cost_q": t["cost"].to_numpy(),
    })  # fmt: skip


def edges(f: pd.DataFrame, tune: np.ndarray) -> dict[str, np.ndarray]:
    return {k: np.nanquantile(f.loc[tune, k], [0.2, 0.4, 0.6, 0.8]) for k in QUANT}


def bucketize(f: pd.DataFrame, ed: dict[str, np.ndarray]) -> pd.DataFrame:
    b = f.copy()
    for k in QUANT:
        q = np.searchsorted(ed[k], f[k].to_numpy(), side="right") + 1
        b[k] = np.where(np.isfinite(f[k].to_numpy()), "q" + q.astype(str), "na")
    return b


def greedy(b: pd.DataFrame, y: np.ndarray) -> tuple[list[tuple[str, str]], float]:
    """Up to ``STEPS`` buckets whose removal raises the mean of ``y`` most; the gain."""
    keep = np.ones(len(y), bool)
    base, chosen = y.mean(), []
    n = len(y)
    for _ in range(STEPS):
        best, best_mask, best_mean = None, None, y[keep].mean()
        for col in b.columns:
            vals = b[col].to_numpy()
            for v in np.unique(vals[keep]):
                m = keep & (vals == v)
                if m.sum() < MIN_SHARE * n:
                    continue
                rest = keep & ~m
                if rest.sum() < MIN_KEEP * n:  # condition 4, inside the search
                    continue
                mu = y[rest].mean()
                if mu > best_mean:
                    best, best_mask, best_mean = (col, v), rest, mu
        if best is None:
            break
        chosen.append(best)
        keep = best_mask
    return chosen, float(y[keep].mean() - base)


def apply(b: pd.DataFrame, chosen: list[tuple[str, str]]) -> np.ndarray:
    keep = np.ones(len(b), bool)
    for col, v in chosen:
        keep &= b[col].to_numpy() != v
    return keep


def screen(b: pd.DataFrame, t: pd.DataFrame, tune: np.ndarray) -> pd.DataFrame:
    rows = []
    y = t["net_slip"].to_numpy()
    for col in b.columns:
        vals = b[col].to_numpy()
        for v in np.unique(vals):
            m = vals == v
            a, o = y[m & tune], y[~m & tune]
            if len(a) < MIN_SHARE * tune.sum():
                continue
            se = np.sqrt(a.var(ddof=1) / len(a) + o.var(ddof=1) / len(o))
            c = y[m & ~tune]
            rows.append({"feature": col, "bucket": v, "share": len(a) / tune.sum(),
                         "tune": a.mean(), "losers": (a < 0).mean(),
                         "t": (a.mean() - o.mean()) / se,
                         "check": c.mean() if len(c) else np.nan, "check_n": len(c)})  # fmt: skip
    return pd.DataFrame(rows).sort_values("tune").reset_index(drop=True)


def build(export: Path) -> str:
    fr = gl.load()
    cx = gl.context(fr)
    t = trades(cx)
    f = features(cx, fr, t)
    tune = (t["year"] <= TUNE_END).to_numpy()
    ed = edges(f, tune)
    b = bucketize(f, ed)
    sc = screen(b, t, tune)
    y = t["net_slip"].to_numpy()
    chosen, gain = greedy(b[tune], y[tune])
    rng = np.random.default_rng(SEED)
    null = [greedy(b[tune], rng.permutation(y[tune]))[1] for _ in range(SHUFFLES)]
    bar = float(np.quantile(null, 0.95))
    keep = apply(b, chosen)
    chk = ~tune

    fx_fr = ge.frames_from_lines(gv.fx_lines(export))
    fx = gl.context(fx_fr)
    ft = trades(fx)
    when = pd.to_datetime(fx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()[ft["i"]]
    ft = ft[when >= np.datetime64(gv.FX_START.tz_convert(None))].reset_index(drop=True)
    fb = bucketize(features(fx, fx_fr, ft), ed)
    fkeep = apply(fb, chosen)
    fy = ft["net_slip"].to_numpy()
    y26 = pd.to_datetime(fx.m["close_utc"], utc=True).dt.year.to_numpy()[ft["i"]] == 2026

    def m(x: np.ndarray) -> str:
        return f"{x.mean():+.3f} ({len(x):,})" if len(x) else "-"

    ok = [gain > bar, y[chk & keep].mean() > y[chk].mean(), fy[fkeep].mean() > fy.mean(),
          keep[tune].mean() >= 0.6]  # fmt: skip
    losers = sc[(sc["tune"] < -0.10) & (sc["check"] < -0.10)]
    lines = [
        "# Gold: what the five strategies' losing trades share (XAUUSD and FxPro)",
        "",
        "_`python -m app research gold-loss build`, registered in `GOLD_LOSS.md` (2026-11-10). "
        "The five's own trades (M8), net R with slip. Buckets and the filter chosen on XAUUSD "
        f"2012-2021; {SHUFFLES} shuffles; read on the check and on FxPro (`{export.name}`)._",
        "",
        f"Trades: {tune.sum():,} on 2012-2021 (losers {(y[tune] < 0).mean():.0%}, mean "
        f"{y[tune].mean():+.3f}), {chk.sum():,} on the check (mean {y[chk].mean():+.3f}).",
        "",
        "## 1. The buckets, worst first (2012-2021)",
        "",
        "| Feature | Bucket | Share | Mean net R | Losers | t against the rest | Check mean "
        "| Check trades |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.feature} | {r.bucket} | {r.share:.0%} | {r.tune:+.3f} | {r.losers:.0%} "
            f"| {r.t:+.1f} | {r.check:+.3f} | {r.check_n:,} |"
            for r in sc.head(25).itertuples()
        ],
        "",
        "The best buckets, for comparison:",
        "",
        "| Feature | Bucket | Share | Mean net R | Losers | t | Check mean |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.feature} | {r.bucket} | {r.share:.0%} | {r.tune:+.3f} | {r.losers:.0%} "
            f"| {r.t:+.1f} | {r.check:+.3f} |"
            for r in sc.tail(8).iloc[::-1].itertuples()
        ],
        "",
        "## 2. The filter",
        "",
        f"Removed: {', '.join(f'{c} = {v}' for c, v in chosen) or 'nothing'}.",
        "",
        "| Period | All trades | Kept | Removed |",
        "| --- | --- | --- | --- |",
        f"| XAUUSD 2012-2021 | {m(y[tune])} | {m(y[tune & keep])} | {m(y[tune & ~keep])} |",
        f"| XAUUSD check | {m(y[chk])} | {m(y[chk & keep])} | {m(y[chk & ~keep])} |",
        f"| FxPro 2016-02 on | {m(fy)} | {m(fy[fkeep])} | {m(fy[~fkeep])} |",
        f"| FxPro 2026 | {m(fy[y26])} | {m(fy[y26 & fkeep])} | {m(fy[y26 & ~fkeep])} |",
        "",
        f"Gain on 2012-2021: {gain:+.3f} R a trade; shuffled 95th percentile {bar:+.3f}.",
        "",
        "| Condition | Met |",
        "| --- | --- |",
        f"| 1. Gain above the shuffled 95th percentile | {'yes' if ok[0] else 'no'} |",
        f"| 2. Check: kept above all | {'yes' if ok[1] else 'no'} |",
        f"| 3. FxPro: kept above all | {'yes' if ok[2] else 'no'} |",
        f"| 4. At least 60% of the trades kept | {'yes' if ok[3] else 'no'} |",
        "",
        f"**Decision (§3): {'adopt as a shadow version' if all(ok) else 'not adopted'}.**",
        "",
        "## 3. Buckets below −0.10 R on 2012-2021 and on the check (candidates, decide nothing)",
        "",
        *(
            [
                f"- {r.feature} = {r.bucket}: {r.tune:+.3f} / {r.check:+.3f} ({r.check_n:,} check "
                "trades)"
                for r in losers.itertuples()
            ]
            if len(losers)
            else ["None."]
        ),  # fmt: skip
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-loss")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
