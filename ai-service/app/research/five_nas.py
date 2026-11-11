"""The five demo strategies on the Nasdaq 100 (``docs/strategies/FIVE_NAS100.md``, registered
2026-11-11).

    python -m app research five-nas build --export <#USNDAQ100 M1 export>

The frozen five (``gold_live.five_trades``) on FxPro's ``#USNDAQ100`` with the index's own costs
(commission 3.0 points a round trip, SL slip 0.5 point), against E0: the same entries with the side
drawn by a fair coin."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "five_nas100_result.md"  # not five_nas100.md: FIVE_NAS100.md on Windows
FIRST_DAY = b"2016.01.04"
START = pd.Timestamp("2016-02-01", tz="UTC")
COMMISSION, SL_SLIP = 3.0, 0.5  # index points: $1.5 a lot each deal, contract size 1
E0_RUNS, SEED = 50, 20261111
NAMES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")


def lines(export: Path):
    with open(export, "rb") as f:
        yield next(f)
        for ln in f:
            if ln[:10] >= FIRST_DAY:
                yield ln


def with_index_costs(fn):
    """Run ``fn`` with the index's commission and SL slip in place of gold's."""

    def run(*a, **k):
        old = gl.COMMISSION, gl.SL_SLIP
        gl.COMMISSION, gl.SL_SLIP = COMMISSION, SL_SLIP
        try:
            return fn(*a, **k)
        finally:
            gl.COMMISSION, gl.SL_SLIP = old

    return run


@with_index_costs
def trades(fr: dict) -> tuple[pd.DataFrame, gl.Ctx]:
    _, every, _, cx = gv.five_trades(fr, start=START)
    return gn.with_day(every, cx), cx


@with_index_costs
def e0(every: pd.DataFrame, cx: gl.Ctx) -> np.ndarray:
    """Mean net R with slip of the same entries with a random side, ``E0_RUNS`` times."""
    rng = np.random.default_rng(SEED)
    sig = every[["strategy", "i", "dir", "entry", "risk", "end"]].copy()
    sig["tp_r"] = np.nan
    out = []
    for _ in range(E0_RUNS):
        s = sig.copy()
        flip = rng.random(len(s)) < 0.5
        s.loc[flip, "dir"] = -s.loc[flip, "dir"]
        # a flipped stop entry fills at the same price: the level, or the open when through
        t = gs.finish(gl.simulate(s, cx, "M8"), cx)
        out.append(t["net_slip"].mean())
    return np.asarray(out)


def build(export: Path) -> str:
    fr = ge.frames_from_lines(lines(export))
    every, cx = trades(fr)
    null = e0(every, cx)
    p95 = float(np.quantile(null, 0.95))
    allm = float(every["net_slip"].mean())
    verdict = "generalises" if allm > 0 and allm > p95 else "does not generalise"
    p = gn.portfolio([every])
    lines_ = [
        "# The five demo strategies on the Nasdaq 100 (unseen instrument)",
        "",
        f"_`python -m app research five-nas build`, registered in `FIVE_NAS100.md` (2026-11-11). "
        f"`{export.name}`, trades {START.date()} to the export's end; commission 3.0 points a "
        "round trip, SL slip 0.5 point; frozen rules, nothing tuned here._",
        "",
        *gs.HEAD,
        gs._row("The five together", every),
        *[gs._row(n, every[every["strategy"] == n]) for n in NAMES],
        "",
        f"Sum {p['sum']:+.1f} R, largest drawdown {p['dd']:.1f} R, gross R "
        f"{every['gross'].mean():+.3f}, cost R {every['cost'].mean():.3f}.",
        "",
        f"E0 (the same entries, a random side, {E0_RUNS} runs): mean {null.mean():+.3f}, "
        f"95th percentile {p95:+.3f}.",
        "",
        f"**Decision (§3): the five {verdict}** (mean {allm:+.3f} against E0's 95th {p95:+.3f}).",
        "",
        *gn._by_year(every),
    ]
    return "\n".join(lines_) + "\n"


# --- RECLAIM at the five's levels (``FIVE_NAS_RECLAIM.md``) ----------------------------------

RECLAIM_REPORT = gl.OUT_DIR / "five_nas_reclaim_result.md"
RECLAIM_SEED = 20261112
SPLIT = 2022


@with_index_costs
def reclaim_trades(cx: gl.Ctx) -> pd.DataFrame:
    from app.research import gold_regime as gr_

    out = []
    for name, (lv, *_rest) in gr_.specs(cx).items():
        if name == "PIVW":  # PIVOT's levels; RECLAIM does not use D, so its trades are PIVOT's
            continue
        sig = gr_.reclaim(cx, name, lv)
        out.append(gs.finish(gl.simulate(sig, cx, "M0"), cx))
    t = pd.concat(out, ignore_index=True)
    when = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True)
    return gn.with_day(t[when >= START].reset_index(drop=True), cx)


@with_index_costs
def reclaim_e0(cx: gl.Ctx, sig: pd.DataFrame) -> np.ndarray:
    """The taken trades' entries, SL distance and target with a random side, ``E0_RUNS`` times."""
    rng = np.random.default_rng(RECLAIM_SEED)
    out = []
    for _ in range(E0_RUNS):
        s = sig.copy()
        flip = rng.random(len(s)) < 0.5
        s.loc[flip, "dir"] = -s.loc[flip, "dir"]
        out.append(gs.finish(gl.simulate(s, cx, "M0"), cx)["net_slip"].mean())
    return np.asarray(out)


def build_reclaim(export: Path) -> str:
    from app.research import gold_regime as gr_

    cx = gl.context(ge.frames_from_lines(lines(export)))
    t = reclaim_trades(cx)
    sig = t[["strategy", "i", "dir", "risk"]].copy()
    sig["entry"] = cx.c[sig["i"].to_numpy()]
    sig["tp_r"] = gr_.RECLAIM_TP
    sig["end"] = cx.deadline[sig["i"].to_numpy()]
    null = reclaim_e0(cx, sig)
    p95 = float(np.quantile(null, 0.95))
    a, b = t[t["year"] < SPLIT], t[t["year"] >= SPLIT]
    ok = [a["net_slip"].mean() > 0, b["net_slip"].mean() > 0, t["net_slip"].mean() > p95]
    p = gn.portfolio([t])
    exits = t["exit"].value_counts(normalize=True).round(2).to_dict()
    lines_ = [
        "# RECLAIM at the five's levels on the Nasdaq 100",
        "",
        "_`python -m app research five-nas reclaim`, registered in `FIVE_NAS_RECLAIM.md` "
        f"(2026-11-11). `{export.name}`, trades {START.date()} to the export's end; commission 3.0 "
        "points a round trip, SL slip 0.5 point; the rule frozen as on gold._",
        "",
        *gs.HEAD,
        gs._row("RECLAIM, all", t),
        gs._row("2016-2021", a),
        gs._row("2022 on", b),
        *[gs._row(n, t[t["strategy"] == n]) for n in NAMES],
        "",
        f"Sum {p['sum']:+.1f} R, largest drawdown {p['dd']:.1f} R, gross R "
        f"{t['gross'].mean():+.3f}, exits {exits}.",
        "",
        f"E0 (the same entries, a random side, {E0_RUNS} runs): mean {null.mean():+.3f}, 95th "
        f"{p95:+.3f}.",
        "",
        "| Condition | Met |",
        "| --- | --- |",
        f"| 1. 2016-2021 > 0 | {'yes' if ok[0] else 'no'} |",
        f"| 2. 2022 on > 0 | {'yes' if ok[1] else 'no'} |",
        f"| 3. Above E0's 95th | {'yes' if ok[2] else 'no'} |",
        "",
        f"**Decision (§2): RECLAIM {'holds' if all(ok) else 'does not hold'} on the Nasdaq.**",
        "",
        *gn._by_year(t),
    ]
    return "\n".join(lines_) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research five-nas")
    ap.add_argument("step", choices=("build", "reclaim"))
    ap.add_argument("--export", type=Path, required=True)
    args = ap.parse_args(argv)
    path, text = (REPORT, build) if args.step == "build" else (RECLAIM_REPORT, build_reclaim)
    path.write_text(text(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return 0
