"""Gold: three time-of-day strategies (``docs/strategies/GOLD_TIME.md``, registered 2026-11-10).

    python -m app research gold-time build                     # XAUUSD: tune, check, report
    python -m app research gold-time fxpro --export <GOLD M1>  # FxPro GOLD, correlations

- **A, intraday momentum:** the sign of the move from 18:00 (S1) or the previous 16:00 (S2) to
  10:00, traded the same way from 10:00, 14:30 or 15:30 to 16:45.
- **B, London to New York:** the sign of 02:00-08:00, with it (CONT) or against it (REV), from
  08:30 to 12:00 or 16:45.
- **C, the night:** long or short from 18:30 or 20:00 to 02:00.

Entries at market at a bar's close, D = 0.75 x ATR(4h), M8 or the SL only (TIME)."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_time_xauusd.md"  # not gold_time.md: GOLD_TIME.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_time_fxpro.md"
CHOICE = gl.STORE / "gold_time_choice.json"
TUNE_END = gc.TUNE_END
MAX_CORR = 0.2  # condition 4: each correlation below +0.2; negative accepted
MGMT = ("M8", "TIME")


def hm(h: int, m: int = 0) -> int:
    return h * 60 + m


GRIDS = {
    "A": [{"signal": s, "entry": e, "mgmt": g}
          for s, e, g in itertools.product(("S1", "S2"), (hm(10), hm(14, 30), hm(15, 30)), MGMT)],
    "B": [{"mode": m, "exit": x, "mgmt": g}
          for m, x, g in itertools.product(("CONT", "REV"), (hm(12), hm(16, 45)), MGMT)],
    "C": [{"side": s, "entry": e, "mgmt": g}
          for s, e, g in itertools.product(("LONG", "SHORT"), (hm(18, 30), hm(20)), MGMT)],
}  # fmt: skip


class Clock:
    """Per trading day (``day_idx``): the bar closing at a New York time, and the first bar."""

    def __init__(self, cx: gl.Ctx) -> None:
        self.cx = cx
        self.n_days = int(cx.day_idx.max()) + 1
        ok = cx.day_idx >= 0
        idx = np.arange(len(cx.c))
        self.first = np.full(self.n_days, -1)
        g = pd.Series(idx[ok]).groupby(cx.day_idx[ok]).min()
        self.first[g.index.to_numpy()] = g.to_numpy()
        self._cache: dict[int, np.ndarray] = {}

    def at(self, minute: int) -> np.ndarray:
        """The bar whose close is at ``minute`` (New York) in each trading day; -1: none."""
        if minute not in self._cache:
            cx = self.cx
            out = np.full(self.n_days, -1)
            m = (cx.ny_min == (minute - 5) % 1440) & (cx.day_idx >= 0)
            out[cx.day_idx[m]] = np.flatnonzero(m)
            self._cache[minute] = out
        return self._cache[minute]


def _sig(cx: gl.Ctx, name: str, k: np.ndarray, d: np.ndarray, end: np.ndarray) -> pd.DataFrame:
    ok = (k >= 0) & (end > k) & (d != 0)
    k, d, end = k[ok], d[ok], end[ok]
    dist = ge.LVL_MULT * cx.atr4h[k]
    good = np.isfinite(dist) & (dist > 0)
    good &= (cx.spread[k] + gl.COMMISSION) / np.where(good, dist, np.nan) <= ge.LVL_CAP
    weekday = cx.weekday[np.where(end >= 0, end, k)]  # the trading day's weekday, at its exit bar
    good &= weekday < 5
    k, d, end, dist = k[good], d[good], end[good], dist[good]
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[k], utc=True)
    s = pd.DataFrame({"strategy": name, "i": k, "dir": d.astype(float), "entry": cx.c[k],
                      "risk": dist, "tp_r": np.nan, "end": end})  # fmt: skip
    return s[t >= gl.START].sort_values("i").reset_index(drop=True)


def signals(cx: gl.Ctx, ck: Clock, name: str, st: dict) -> pd.DataFrame:
    days = np.arange(ck.n_days)
    if name == "A":
        if st["signal"] == "S1":
            f = ck.first
            s0 = np.where(f >= 0, cx.o[np.maximum(f, 0)], np.nan)
        else:
            p = np.r_[-1, ck.at(hm(16))[:-1]]
            s0 = np.where(p >= 0, cx.c[np.maximum(p, 0)], np.nan)
        a10 = ck.at(hm(10))
        s1 = np.where(a10 >= 0, cx.c[np.maximum(a10, 0)], np.nan)
        d = np.nan_to_num(np.sign(s1 - s0))
        k = ck.at(st["entry"])
        end = np.where(k >= 0, cx.deadline[np.maximum(k, 0)], -1)
    elif name == "B":
        a2, a8 = ck.at(hm(2)), ck.at(hm(8))
        ok = (a2 >= 0) & (a8 >= 0)
        d = np.where(ok, np.sign(cx.c[np.maximum(a8, 0)] - cx.c[np.maximum(a2, 0)]), 0.0)
        d = d if st["mode"] == "CONT" else -d
        k = ck.at(hm(8, 30))
        if st["exit"] == hm(16, 45):
            end = np.where(k >= 0, cx.deadline[np.maximum(k, 0)], -1)
        else:
            end = ck.at(st["exit"])
    else:
        d = np.full(len(days), 1.0 if st["side"] == "LONG" else -1.0)
        k, end = ck.at(st["entry"]), ck.at(hm(2))
    return _sig(cx, name, k, d, end)


def run(cx: gl.Ctx, ck: Clock, name: str, st: dict) -> pd.DataFrame:
    bundle = "M8" if st["mgmt"] == "M8" else "M0"
    t = gl.simulate(signals(cx, ck, name, st), cx, bundle)
    return gn.with_day(gs.finish(t, cx), cx)


def label(st: dict) -> str:
    def v(x):
        return f"{x // 60:02d}:{x % 60:02d}" if isinstance(x, int) else str(x)

    return " / ".join(v(x) for x in st.values())


def tune(cx: gl.Ctx, ck: Clock, name: str) -> pd.DataFrame:
    days = len(np.unique(cx.day_idx[(cx.m["close_utc"] >= gl.START).to_numpy()]))
    rows = []
    for st in GRIDS[name]:
        t = run(cx, ck, name, st)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({"setting": st, "label": label(st), "per_day": len(t) / days,
                     **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


def _grid(g: pd.DataFrame) -> list[str]:
    return [
        "| Setting | Trades a day | Tune trades | Tune net | Tune years + | Tune cost R "
        "| Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.label} | {r.per_day:.2f} | {r.tune_trades:,} | {r.tune_net:+.3f} "
            f"| {r.tune_years_pos:.0%} | {r.tune_cost:.3f} | {r.check_trades:,} "
            f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {r.check_net_slip:+.3f} "
            f"| {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],
    ]


TITLES = {"A": "intraday momentum", "B": "London to New York", "C": "the night"}


def build() -> str:
    cx = gl.context(gl.load())
    ck = Clock(cx)
    day = gn.day_strategies(cx)
    choice: dict = {}
    lines = [
        "# Gold: three time-of-day strategies, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-time build`, registered in `GOLD_TIME.md` (2026-11-10). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; D = 0.75 x ATR(4h); cost = the entry bar's "
        "spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 "
        "to 2026-01-09. Seen data: optimistic. The lockbox was not read._",
    ]
    for n, name in enumerate(("A", "B", "C"), start=1):
        g = tune(cx, ck, name)
        ok = g[g["eligible"]]
        lines += ["", f"## {n}. {name}: {TITLES[name]} (by net R on 2012-2021)", "", *_grid(g), ""]
        if not len(ok):
            lines.append(f"**No setting qualifies: {name} is dropped.**")
            continue
        st = ok.iloc[0]["setting"]
        choice[name] = st
        t = run(cx, ck, name, st)
        corr = gn.correlations(t, day)
        lines += [
            f"Chosen: {label(st)}.",
            "",
            *gs.HEAD,
            gs._row("2012-2021", t[t["year"] <= TUNE_END]),
            gs._row("Check", t[t["year"] > TUNE_END]),
            gs._row("Buys", t[t["dir"] > 0]),
            gs._row("Sells", t[t["dir"] < 0]),
            "",
            "Daily net R correlation with the five (decides nothing here): "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + ".",
            "",
            *gn._by_year(t),
        ]
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if not choice:
        return "# Gold: time-of-day strategies on FxPro's GOLD feed\n\nAll dropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    ck = Clock(cx)

    def since(t: pd.DataFrame) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= gv.FX_START]

    day = {k: since(d) for k, d in gn.day_strategies(cx).items()}
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    lines = [
        "# Gold: time-of-day strategies, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-time fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Settings chosen on XAUUSD 2012-2021._",
        "",
        *gs.HEAD,
    ]
    trades = {}
    for name, st in choice.items():
        t = since(run(cx, ck, name, st))
        trades[name] = t
        in26 = t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= exam]
        lines += [gs._row(f"{name} ({label(st)})", t), gs._row(f"{name}, 2026-01-12 on", in26)]
    lines.append("")
    for name, t in trades.items():
        corr = gn.correlations(t, day)
        sm = gs.summary(t)
        met = sm["net_slip"] > 0 and all(v < MAX_CORR for v in corr.values())
        lines += [
            f"**{name}**: net with slip {sm['net_slip']:+.3f}; daily correlation "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + f"; conditions 3 and 4: **{'met' if met else 'not met'}**.",
            "",
            *gn._by_year(t),
            "",
        ]
    five = gn.portfolio(list(day.values()))
    lines += [
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        f"| The five | {five['trades']:,} | {five['mean']:+.3f} | {five['sum']:+.1f} "
        f"| {five['dd']:.1f} |",
    ]
    for name, t in trades.items():
        p = gn.portfolio([*day.values(), t])
        lines.append(f"| The five and {name} | {p['trades']:,} | {p['mean']:+.3f} "
                     f"| {p['sum']:+.1f} | {p['dd']:.1f} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-time")
    ap.add_argument("step", choices=("build", "fxpro"))
    ap.add_argument("--export", type=Path, help="fxpro: the GOLD M1 export")
    args = ap.parse_args(argv)
    if args.step == "build":
        REPORT.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
    else:
        FX_REPORT.write_text(fxpro(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {FX_REPORT}")
    return 0
