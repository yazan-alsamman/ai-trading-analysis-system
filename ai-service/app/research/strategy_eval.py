"""Stage C: the strategy tests of families A and B under M0 (docs/strategies/PREREG.md, sections
8 and 10; trials 11-18).

    python -m app research evaluate                 # every instrument in the store

**Runs only after approval, on the frozen rules.** Refused while the approval date or the seeds of
the preregistration are empty, while any rule file differs from the frozen commit (``RULE_PATHS``
of ``app.strategies.cli`` and, here, the management engine and the label code it uses:
``EVAL_PATHS``), or while ``docs/strategies/counts.md`` was made on another frozen commit.
delta*_S comes from that file (section 8: filled from the pre-approval counts).

**Trades.** Per strategy and instrument, the armed candidates with entry from 2018-01-01 under
M0's one-active-trade rule (``app.management.book``), on bars loaded only to 2024-07-01 (warm-up
from 2017, as the post-approval counts); unresolved trades are excluded and counted. x = net R
(costs, SL slippage) + the decision swap scenario (W1 by the trade's own exit time, at the price
of each rollover; W2 is not available). W0, W3 and the 2x cost stress are kept for the reports.
The sensitivities 1 and 2 use a second book with entries from 2012-01-01.

**E0** (section 8, as ``app.research.baselines``): for each trade, ``REPS`` random trades on the
same instrument and entry frame, a bar whose New York year and hour are the trade's, a fair coin
for the direction, the same risk in ATR units (the strategy's entry-frame ATR), the same TP in R
(the trade's R multiple), the same cost filter, the same session end (a bar with no time left is
not drawn), M0 labels, costs and the same swap scenario. A rejected or unresolved draw is redrawn,
up to ``MAX_DRAWS`` times. e_i = the mean over the replications; d_i = x_i - e_i. A trade without
any E0 draw is left out of the test and counted.

**Test** (section 8): ``decide.strategy_test`` with 4-week blocks and B = 20,000; Holm within
family A (S1-S6) and B (S7-S8); ``decide.classify`` with delta*_S. A passed strategy waits for its
holdout check (section 10), which is not run here. Reported, never decided on: Bonferroni lower
bounds, 1-, 2- and 8-week blocks, the 2x cost stress, every swap scenario, sensitivities 1-3,
without first-Friday 08:30 New York trades, per instrument and year, the exit mix, E0's Monte
Carlo SE and replication p-value, and the Deflated Sharpe with N = 25.

Writes ``docs/strategies/evaluation.md`` and ``eval_<S>.md``, and the trades and E0 draws to
``data/processed/stage_c_*.parquet`` (untracked). Nothing after 2024-07-01 is loaded."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import trading_indicators as ti
from scipy import stats

from app.config import (
    Bundle,
    Instrument,
    Rules,
    SignalSpec,
    bundles,
    common,
    instruments,
    rules,
    signal_specs,
)
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ, market_holidays
from app.management.book import manager, one_active
from app.management.counts import WARM_UP, approved
from app.management.engine import Market, manage
from app.research import decide
from app.setups.costs import round_trip
from app.strategies import frames as research_frames
from app.strategies import swap
from app.strategies.base import STEP, Candidate, at_time, local
from app.strategies.cli import OUT_DIR, PREREG, ROOT, RULE_PATHS, frozen_commit, load_swaps
from app.strategies.counts import bounds
from app.strategies.rules import Frames, candidates

REPS = 200
BOOT = 20_000
MAX_DRAWS = 50
SENS_WEEKS = (1, 2, 8)
N_TRIALS = 25  # Deflated Sharpe (PREREG section 15)
START_2012 = pd.Timestamp("2012-01-01", tz="UTC")
SWAPS = OUT_DIR / "mt5" / "swaps_2026-10-28.json"
COUNTS = OUT_DIR / "counts.md"
TRIAL = {"S1": 11, "S2": 12, "S3": 13, "S4": 14, "S5": 15, "S6": 16, "S7": 17, "S8": 18}
# The management engine and the code it reads are rules too (section 15), outside RULE_PATHS.
EVAL_PATHS = (
    *RULE_PATHS,
    "ai-service/app/management",
    "ai-service/app/setups/labels.py",
    "ai-service/app/smc/primitives.py",
)


# --- registration ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def seeds(prereg: Path = PREREG) -> tuple[int, int]:
    """(E0, bootstrap) from the preregistration's "Seeds (E0, bootstrap)" field."""
    m = re.search(
        r"^\| Seeds \(E0, bootstrap\) \| (\d+)\D+(\d+) \|$", prereg.read_text(encoding="utf-8"),
        re.M,
    )  # fmt: skip
    if not m:
        raise ValueError("the seeds are not fixed in PREREG.md ('Seeds (E0, bootstrap)')")
    return int(m.group(1)), int(m.group(2))


def deltas(counts_md: Path, commit: str) -> dict[str, float]:
    """delta*_S from the pre-approval counts, which must be of the frozen ``commit``."""
    text = counts_md.read_text(encoding="utf-8")
    if f"| Rules frozen at commit | `{commit}` |" not in text:
        raise ValueError(f"{counts_md.name} was not made on the frozen commit {commit[:12]}")
    section = text.split("## Allowance", 1)[1]
    out = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 4 and re.fullmatch(r"S\d", cells[0]):
            out[cells[0]] = float(cells[3]) if cells[3] else np.nan
    return out


def registered(prereg: Path = PREREG, repo: Path = ROOT.parent) -> tuple[str, str, tuple[int, int]]:
    """The frozen commit, HEAD and the seeds, or an error: not approved, seeds empty, or a rule
    file (``EVAL_PATHS``) differing from the frozen commit."""
    if not approved(prereg):
        raise PermissionError("Stage C needs the approved preregistration (approval date)")
    commit, head = frozen_commit(prereg, repo)
    changed = _git(repo, "diff", "--name-only", commit, "--", *EVAL_PATHS).split()
    changed += _git(repo, "ls-files", "--others", "--exclude-standard", "--", *EVAL_PATHS).split()
    if changed:
        raise ValueError(f"rule files differ from the frozen commit {commit[:12]}: {changed}")
    return commit, head, seeds(prereg)


# --- trades ---------------------------------------------------------------------------------

TRADE_COLUMNS = [
    "symbol", "strategy", "family", "type", "idx", "direction", "signal_utc", "entry_utc",
    "exit_utc", "state", "reason", "k", "risk", "atr", "spread", "entry", "net_w0", "net_2x",
    "w1", "w3", "x", "x_2x",
]  # fmt: skip


def trades(
    frames: Frames,
    inst: Instrument,
    spec: SignalSpec,
    rp: Rules,
    m0: Bundle,
    sw: swap.SwapSpec,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, int]:
    """M0 trades of one strategy on one instrument with entry from ``start`` (one active trade at
    a time), and the number of candidates left undecided after an unresolved trade."""
    e = frames[spec.frame]
    close = e["close_utc"]
    price_at = swap.close_before(e)
    cs = [
        c
        for c in candidates(frames, inst, spec)
        if c.state == "ARMED" and close.iloc[c.idx] >= start
    ]
    rows, undecided = [], 0
    for c, o in one_active(cs, manager(frames, inst, spec, rp, m0)):
        if o is None:
            undecided += c.reason != "position_open"
            continue
        t = close.iloc[c.idx]
        row = {
            "symbol": inst.symbol, "strategy": spec.name, "family": spec.family,
            "type": spec.type, "idx": c.idx, "direction": c.direction, "signal_utc": c.ts_utc,
            "entry_utc": t, "k": c.r_multiple, "risk": c.risk, "atr": c.atr, "spread": c.spread,
            "entry": c.entry,
        }  # fmt: skip
        if o.state != "CLOSED":
            rows.append({**row, "state": "unresolved", "reason": "", "exit_utc": pd.NaT})
            continue
        x = pd.Timestamp(o.exit_ns, tz="UTC")
        w1 = swap.swap_r(sw, c.direction, t, x, c.risk, c.entry, price_at)
        w3 = swap.stress_r(sw, t, x, c.risk, c.entry)
        rows.append(
            {
                **row,
                "state": "resolved",
                "reason": o.reason,
                "exit_utc": x,
                "net_w0": o.net_r(),
                "net_2x": o.net_r(2),
                "w1": w1,
                "w3": w3,
                "x": o.net_r() + swap.decision_r(w1, None),
                "x_2x": o.net_r(2) + swap.decision_r(w1, None),
            }  # fmt: skip
        )
    out = pd.DataFrame(rows).reindex(columns=TRADE_COLUMNS)
    for col in ("signal_utc", "entry_utc", "exit_utc"):
        out[col] = pd.to_datetime(out[col], utc=True)
    return out, undecided


# --- E0 -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rollovers:
    """The rollover instants of one entry frame's span, computed once with ``swap.instants``, and
    the price at each (``swap.close_before``). ``w1`` adds the same terms in the same order as
    ``swap.swap_r``, so it returns the same float, without rebuilding the instants for every
    trade (performance only; ``tests/test_strategy_eval.py`` checks the equality). Outside the
    span it calls ``swap.swap_r``."""

    spec: swap.SwapSpec
    lo: int  # ns: instants in (lo, hi]
    hi: int
    at: np.ndarray  # ns
    weight: np.ndarray
    price: np.ndarray
    price_at: Callable[[pd.Timestamp], float]

    @classmethod
    def of(cls, frame: pd.DataFrame, sw: swap.SwapSpec) -> Rollovers:
        price_at = swap.close_before(frame)
        lo = frame["close_utc"].iloc[0] - pd.Timedelta(days=1)
        hi = frame["close_utc"].iloc[-1] + pd.Timedelta(days=30)
        t = swap.instants(lo, hi, sw)
        price = []
        for at in t["at"]:
            try:
                price.append(price_at(at))
            except ValueError:  # before the first bar: no trade is open then
                price.append(np.nan)
        at_ns = pd.DatetimeIndex(t["at"]).as_unit("ns").asi8
        return cls(sw, lo.value, hi.value, at_ns, t["weight"].to_numpy(float),
                   np.array(price, float), price_at)  # fmt: skip

    def w1(
        self,
        direction: str,
        entry: pd.Timestamp,
        exit_: pd.Timestamp,
        risk: float,
        price_open: float,
    ) -> float:
        if entry.value < self.lo or exit_.value > self.hi:
            return swap.swap_r(self.spec, direction, entry, exit_, risk, price_open, self.price_at)
        a = int(np.searchsorted(self.at, entry.value, side="right"))
        b = int(np.searchsorted(self.at, exit_.value, side="right"))
        total = 0.0
        for i in range(a, b):
            total += float(self.weight[i]) * swap.per_night_r(
                self.spec, direction, float(self.price[i]), price_open, risk
            )
        return total


@dataclass
class Pool:
    """Random entry bars of one strategy's entry frame, by New York (year, hour)."""

    frame: pd.DataFrame
    spec: SignalSpec
    atr: np.ndarray
    spread: np.ndarray
    close: np.ndarray
    deadline: np.ndarray  # ns, 0 when the type has no session end
    bars: dict[tuple[int, int], np.ndarray]
    markets: dict[str, Market]
    price_at: object
    rollovers: Rollovers | None = None  # None: swap.swap_r for every draw


def pool(frames: Frames, spec: SignalSpec, rp: Rules, sw: swap.SwapSpec | None = None) -> Pool:
    e = frames[spec.frame]
    n = len(e)
    a = ti.atr(e, spec.params["atr_period"]).to_numpy()
    col = "spread_mean"
    spread = e[col].fillna(0.0).to_numpy(float) if col in e else np.zeros(n)
    mins, days = local(e["ts_utc"], MARKET_TZ)
    ny = e["ts_utc"].dt.tz_convert(MARKET_TZ)
    weekday = ny.dt.day_of_week.to_numpy() < 5
    years = ny.dt.year.to_numpy()
    hol = np.zeros(n, bool)
    if n:
        h = sorted(market_holidays(int(years.min()), int(years.max())))
        hol = np.isin(days, np.array(h, dtype="datetime64[ns]"))
    deadline = np.zeros(n, dtype=np.int64)
    if spec.session_end is not None and n:
        uniq = {d: at_time(d, spec.session_end, MARKET_TZ).value for d in np.unique(days)}
        deadline = np.array([uniq[d] for d in days], dtype=np.int64)
    close_ns = pd.DatetimeIndex(e["close_utc"]).as_unit("ns").asi8
    step = STEP[spec.frame].value
    time_left = (deadline == 0) | (close_ns + step <= deadline)
    ok = ~np.isnan(a) & ~hol & weekday & time_left & (np.arange(n) + 1 < n)
    keys = pd.DataFrame({"y": years, "h": ny.dt.hour.to_numpy(), "j": np.arange(n)})[ok]
    return Pool(
        e, spec, a, spread, e["close"].to_numpy(float), deadline,
        {k: g["j"].to_numpy() for k, g in keys.groupby(["y", "h"])},
        {d: Market.of(e, d, spec.frame, rp) for d in ("buy", "sell")}, swap.close_before(e),
        Rollovers.of(e, sw) if sw is not None and n else None,
    )  # fmt: skip


def e0_draw(
    p: Pool,
    year: int,
    hour: int,
    risk_atr: float,
    k: float,
    rng: np.random.Generator,
    inst: Instrument,
    rp: Rules,
    m0: Bundle,
    sw: swap.SwapSpec,
    cost_filter_r: float,
) -> float | None:
    """x of one random trade (section 8), or None after ``MAX_DRAWS`` rejected draws."""
    cands = p.bars.get((year, hour))
    if cands is None:
        return None
    for _ in range(MAX_DRAWS):
        j = int(cands[rng.integers(len(cands))])
        d = "buy" if rng.random() < 0.5 else "sell"
        s = 1.0 if d == "buy" else -1.0
        risk = risk_atr * float(p.atr[j])
        if not risk > 0:
            continue
        spread = float(p.spread[j])
        if (round_trip(spread, inst) + inst.sl_slippage) / risk > cost_filter_r:
            continue
        entry = float(p.close[j])
        deadline = pd.Timestamp(int(p.deadline[j]), tz="UTC") if p.deadline[j] else None
        c = Candidate(
            p.spec.name, j, p.frame["ts_utc"].iloc[j], d, "ARMED", "", entry, entry - s * risk,
            entry + s * k * risk, risk, k, spread, float(p.atr[j]), p.spec.horizon_bars, deadline,
        )  # fmt: skip
        o = manage(p.markets[d], c, m0, rp, inst)
        if o.state != "CLOSED":
            continue
        t, x = p.frame["close_utc"].iloc[j], pd.Timestamp(o.exit_ns, tz="UTC")
        if p.rollovers is not None and p.rollovers.spec == sw:
            w1 = p.rollovers.w1(d, t, x, risk, entry)
        else:
            w1 = swap.swap_r(sw, d, t, x, risk, entry, p.price_at)
        return o.net_r() + swap.decision_r(w1, None)
    return None


def e0(
    book: pd.DataFrame,
    pools: dict[tuple[str, str], Pool],
    reps: int,
    rng: np.random.Generator,
    rp: Rules,
    m0: Bundle,
    sw: dict[str, swap.SwapSpec],
    cost_filter_r: float,
) -> np.ndarray:
    """The E0 draws of every resolved trade of ``book``: an array (trades x reps), NaN where a
    draw failed. Replication by replication, trades in the book's order (fixed seed)."""
    ny = pd.DatetimeIndex(book["signal_utc"]).tz_convert(MARKET_TZ)
    years, hours = ny.year.to_numpy(), ny.hour.to_numpy()  # once: ny.year[i] rebuilds the array
    keys = list(zip(book["symbol"], book["strategy"], strict=True))
    out = np.full((len(book), reps), np.nan)
    risk_atr = (book["risk"] / book["atr"]).to_numpy(float)
    k = book["k"].to_numpy(float)
    start = time.monotonic()
    for rep in range(reps):
        for i, (sym, name) in enumerate(keys):
            x = e0_draw(
                pools[sym, name], int(years[i]), int(hours[i]), risk_atr[i], k[i], rng,
                instruments()[sym], rp, m0, sw[sym], cost_filter_r,
            )  # fmt: skip
            if x is not None:
                out[i, rep] = x
        done = time.monotonic() - start
        left = done / (rep + 1) * (reps - rep - 1)
        print(f"E0 replication {rep + 1}/{reps} ({len(keys)} trades): {done / 60:.1f} min,"
              f" about {left / 60:.0f} min left", file=sys.stderr, flush=True)  # fmt: skip
    return out


# --- tests and reports ----------------------------------------------------------------------


def first_friday_news(entry: pd.Series, exit_: pd.Series) -> np.ndarray:
    """Trades open at 08:30 New York on the first Friday of a month (the US jobs report)."""
    out = np.zeros(len(entry), bool)
    for i, (a, b) in enumerate(zip(entry, exit_, strict=True)):
        day = a.tz_convert(MARKET_TZ).normalize()
        for d in pd.date_range(day, b.tz_convert(MARKET_TZ).normalize(), freq="D"):
            if d.day_of_week == 4 and d.day <= 7:
                t = (d + pd.Timedelta(hours=8, minutes=30)).tz_convert("UTC")
                out[i] |= a < t <= b
    return out


def bonferroni_lower(x: np.ndarray, blocks: np.ndarray, m: int, boot: int, seed: int) -> tuple:
    (xs,), k = decide.bootstrap([x], blocks, boot, np.random.default_rng(seed))
    a = decide.ALPHA / m
    return float(np.quantile(xs, a)), float(x.mean() - stats.t.ppf(1 - a, k - 1) * xs.std(ddof=1))


def tested(g: pd.DataFrame, boot: int, seed: int, weeks: int = 4) -> decide.StrategyTest | None:
    if len(g) < 2:
        return None
    return decide.strategy_test(
        g["x"].to_numpy(), g["d"].to_numpy(), g["entry_utc"], boot, seed, weeks
    )


@dataclass
class Result:
    name: str
    spec: SignalSpec
    test: decide.StrategyTest | None
    adjusted: float
    classification: str
    delta: float
    primary: pd.DataFrame  # resolved trades with an E0 mean (x, e, d)
    unresolved: int
    undecided: int
    no_e0: int
    rep_means: np.ndarray
    sens: dict[str, tuple[pd.DataFrame, decide.StrategyTest | None]]
    blocks: dict[int, float]
    lower: tuple[float, float]
    dsr: dict


def _f(v: float, sign: bool = True) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return f"{v:+.3f}" if sign else f"{v:.3f}"


def _p(v: float | None) -> str:
    return "" if v is None or np.isnan(v) else f"{v:.4f}"


def strategy_report(r: Result, commit: str, head: str, seeds_: tuple[int, int], boot: int,
                    reps: int) -> str:  # fmt: skip
    t, g = r.test, r.primary
    lines = [
        f"# Stage C: {r.name} (trial {TRIAL.get(r.name, '')}, family {r.spec.family},"
        f" {r.spec.type}, {r.spec.frame})",
        "",
        f"_Generated by `python -m app research evaluate`. Rules frozen at `{commit}`, code"
        f" `{head}`; seeds E0 {seeds_[0]}, bootstrap {seeds_[1]}; B = {boot}, E0 replications"
        f" {reps}. Primary period 2018-01-01 to 2024-07-01, bars loaded to 2024-07-01. Swap: the"
        " decision scenario (W1, estimated retrospective swap). The holdout is not read here._",
        "",
        "## Decision (PREREG section 8)",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Trades in the test (n) | {len(g)} |",
        f"| Excluded: unresolved at the load limit / no E0 draw | {r.unresolved} / {r.no_e0} |",
        f"| Undecided after an unresolved trade | {r.undecided} |",
    ]
    if t is not None:
        lines += [
            f"| Blocks K (4 weeks); method condition K >= 30 | {t.k};"
            f" {'met' if t.method_ok else 'not met'} |",
            f"| Mean net R x | {_f(t.mean_x)} (95% {_f(t.ci_x[0])} to {_f(t.ci_x[1])}) |",
            f"| Mean d = x - e | {_f(t.mean_d)} (95% {_f(t.ci_d[0])} to {_f(t.ci_d[1])}) |",
            f"| p1 / p2 for x | {_p(t.p1_x)} / {_p(t.p2_x)} |",
            f"| p1 / p2 for d | {_p(t.p1_d)} / {_p(t.p2_d)} |",
            f"| p_S (max of the four) | {_p(t.p)} |",
            f"| Holm-adjusted p (family {r.spec.family}) | {_p(r.adjusted)} |",
            f"| U_S = max(U1, U2) | {_f(t.upper)} |",
            f"| delta*_S | {_f(r.delta, False)} |",
            f"| Bonferroni one-sided lower bound of mean x (percentile / t) | {_f(r.lower[0])}"
            f" / {_f(r.lower[1])} |",
        ]  # fmt: skip
    lines += [
        f"| **Result** | **{r.classification}**"
        + (" (status waits for the holdout check, section 10)" * (r.classification == "passed"))
        + " |",
        "",
        "## Reported, not decided on",
        "",
    ]  # fmt: skip
    if t is None:
        return "\n".join(lines + ["No trades.", ""])
    e = g["e"].to_numpy()
    se = (
        float(np.nanstd(r.rep_means, ddof=1) / np.sqrt(len(r.rep_means)))
        if len(r.rep_means) > 1
        else np.nan
    )
    rep_p = (1 + int((r.rep_means >= t.mean_x).sum())) / (1 + len(r.rep_means))
    lines += [
        "| Quantity | Value |",
        "| --- | --- |",
        f"| E0 mean e (Monte Carlo SE) | {_f(float(np.mean(e)))} ({_f(se, False)}) |",
        f"| Replication p (share of E0 replication means >= mean x) | {_p(rep_p)} |",
        f"| Mean net R under W0 / W1 / W3 / decision | {_f(g['net_w0'].mean())} /"
        f" {_f((g['net_w0'] + g['w1']).mean())} / {_f((g['net_w0'] + g['w3']).mean())} /"
        f" {_f(g['x'].mean())} |",
        f"| Mean net R at 2x costs | {_f(g['x_2x'].mean())} |",
        *[f"| p_S with {w}-week blocks | {_p(p)} |" for w, p in r.blocks.items()],
        f"| Deflated Sharpe (N = {N_TRIALS}): per-trade Sharpe, expected max, DSR |"
        f" {_f(r.dsr['sharpe'])}, {_f(r.dsr['sr0'])}, {_p(r.dsr['dsr'])} |",
        f"| TP rate | {(g['reason'] == 'tp').mean():.1%} |",
        "",
        "Sensitivities (section 10; unadjusted p_S):",
        "",
        "| Set | n | Mean x | Mean d | p_S |",
        "| --- | --- | --- | --- | --- |",
    ]  # fmt: skip
    for name, (sub, st) in r.sens.items():
        lines.append(
            f"| {name} | {len(sub)} | {_f(sub['x'].mean()) if len(sub) else ''} |"
            f" {_f(sub['d'].mean()) if len(sub) else ''} | {_p(st.p) if st else ''} |"
        )
    lines += [
        "",
        "Exit mix:",
        "",
        "| Reason | Trades | Share | Mean x |",
        "| --- | --- | --- | --- |",
    ]
    for k, q in g.groupby("reason"):
        lines.append(f"| {k} | {len(q)} | {len(q) / len(g):.0%} | {_f(q['x'].mean())} |")
    lines += [
        "",
        "Per instrument:",
        "",
        "| Instrument | n | Mean x | Mean d |",
        "| --- | --- | --- | --- |",
    ]
    for k, q in g.groupby("symbol"):
        lines.append(f"| {k} | {len(q)} | {_f(q['x'].mean())} | {_f(q['d'].mean())} |")
    lines += ["", "Per year:", "", "| Year | n | Mean x | Mean d |", "| --- | --- | --- | --- |"]
    for k, q in g.groupby(g["entry_utc"].dt.year):
        lines.append(f"| {k} | {len(q)} | {_f(q['x'].mean())} | {_f(q['d'].mean())} |")
    return "\n".join([*lines, ""])  # fmt: skip


def summary_report(results: list[Result], commit: str, head: str, run_date: str) -> str:
    lines = [
        "# Stage C: strategy tests, families A and B (trials 11-18)",
        "",
        f"_Generated by `python -m app research evaluate` on {run_date}. Rules frozen at"
        f" `{commit}`,"
        f" code `{head}`. Holm within each family, one-sided alpha 0.05. **A passed strategy is"
        " not validated yet:** its status waits for the single holdout check (section 10). Every"
        ' other result is served marked "no proven edge"._',
        "",
        "| Trial | Strategy | Family | Type | n | K | Mean x | Mean d | p_S | Holm p | U_S |"
        " delta* | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        t = r.test
        lines.append(
            f"| {TRIAL.get(r.name, '')} | {r.name} | {r.spec.family} | {r.spec.type} |"
            f" {len(r.primary)} | {t.k if t else 0} | {_f(t.mean_x) if t else ''} |"
            f" {_f(t.mean_d) if t else ''} | {_p(t.p) if t else ''} | {_p(r.adjusted)} |"
            f" {_f(t.upper) if t else ''} | {_f(r.delta, False)} | {r.classification} |"
        )
    lines += [
        "",
        "Rows for `docs/phase3/TRIALS.md` (trials 11-18) are copied from this table; N for the"
        f" Deflated Sharpe is {N_TRIALS}.",
        "",
    ]
    return "\n".join(lines)


# --- the run --------------------------------------------------------------------------------


def evaluate(
    frames_by_symbol: dict[str, Frames],
    swaps: dict[str, swap.SwapSpec],
    deltas_: dict[str, float],
    seeds_: tuple[int, int],
    reps: int = REPS,
    boot: int = BOOT,
) -> tuple[list[Result], pd.DataFrame, np.ndarray]:
    """Families A and B on the given frames (bars to 2024-07-01 only)."""
    primary, holdout, _ = bounds()
    for sym, f in frames_by_symbol.items():
        for tf, df in f.items():
            if len(df) and df["close_utc"].max() > holdout:
                raise ValueError(f"{sym} {tf}: bars after the holdout start {holdout}")
    specs = signal_specs()
    rp, m0 = rules(), bundles()["M0"]
    cost_filter_r = common().cost_filter_r
    from app.research.meta import deflated_sharpe  # lightgbm and sklearn: research extras only

    books, undecided, pools = [], {}, {}
    for sym, f in sorted(frames_by_symbol.items()):
        inst = instruments()[sym]
        for name, sp in sorted(specs.items()):
            for label, start in (("primary", primary), ("from_2012", START_2012)):
                b, u = trades(f, inst, sp, rp, m0, swaps[sym], start)
                undecided[name, label] = undecided.get((name, label), 0) + u
                books.append(b.assign(book=label))
            pools[sym, name] = pool(f, sp, rp, swaps[sym])
        print(f"{sym}: trades and E0 pools ready", file=sys.stderr, flush=True)
    book = pd.concat(books, ignore_index=True)
    resolved = book[book["state"] == "resolved"]
    keys = ["symbol", "strategy", "idx", "direction"]
    uniq = resolved.drop_duplicates(keys).reset_index(drop=True)
    draws = e0(uniq, pools, reps, np.random.default_rng(seeds_[0]), rp, m0, swaps, cost_filter_r)
    with np.errstate(all="ignore"):
        uniq = uniq.assign(e=np.nanmean(draws, axis=1) if reps else np.nan)
    book = book.merge(uniq[[*keys, "e"]], on=keys, how="left")
    book["d"] = book["x"] - book["e"]
    rep_idx = {tuple(r): i for i, r in enumerate(uniq[keys].itertuples(index=False))}

    results = []
    for name, sp in sorted(specs.items()):
        mine = book[book["strategy"] == name]
        prim = mine[mine["book"] == "primary"]
        res = prim[prim["state"] == "resolved"]
        g = res[res["e"].notna()].sort_values("entry_utc").reset_index(drop=True)
        rows = [rep_idx[tuple(r)] for r in g[keys].itertuples(index=False)]
        with np.errstate(all="ignore"):
            rep_means = np.nanmean(draws[rows], axis=0) if rows else np.array([])
        t = tested(g, boot, seeds_[1])
        m = sum(x.family == sp.family for x in specs.values())
        early = mine[(mine["book"] == "from_2012") & (mine["state"] == "resolved")]
        early = early[early["e"].notna()].sort_values("entry_utc")
        sens = {}
        for label, sub in (
            ("Sensitivity 1: XAUUSD from 2012", early[early["symbol"] == "XAUUSD"]),
            ("Sensitivity 2: all from 2012", early),
            ("Sensitivity 3: without EURUSD 2021-2023", g[~((g["symbol"] == "EURUSD")
                & g["entry_utc"].dt.year.between(2021, 2023))]),
            ("Without first-Friday 08:30 New York",
             g[~first_friday_news(g["entry_utc"], g["exit_utc"])]),
        ):  # fmt: skip
            sens[label] = (sub, tested(sub, boot, seeds_[1]))
        blocks = {
            w: (tested(g, boot, seeds_[1], w).p if len(g) > 1 else np.nan) for w in SENS_WEEKS
        }
        lower = (np.nan, np.nan)
        if t is not None:
            lower = bonferroni_lower(
                g["x"].to_numpy(), decide.block_ids(g["entry_utc"]), m, boot, seeds_[1]
            )
        results.append(
            Result(
                name, sp, t, np.nan, "", deltas_.get(name, np.nan), g,
                int((prim["state"] == "unresolved").sum()), undecided[name, "primary"],
                int(res["e"].isna().sum()), rep_means, sens, blocks, lower,
                deflated_sharpe(g["x"].to_numpy(), N_TRIALS),
            )
        )  # fmt: skip
    for fam in ("A", "B"):
        group = [r for r in results if r.spec.family == fam]
        adj = decide.holm({r.name: (r.test.p if r.test else 1.0) for r in group})
        for r in group:
            r.adjusted = adj[r.name]
            ok = r.test is not None and r.test.method_ok
            upper = r.test.upper if r.test else np.inf
            r.classification = decide.classify(r.adjusted, ok, upper, r.delta)
    return results, book, draws


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research evaluate")
    ap.add_argument("--symbol", action="append")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    try:
        commit, head, seeds_ = registered()
        deltas_ = deltas(COUNTS, commit)
    except (PermissionError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    _, holdout, _ = bounds()
    symbols = args.symbol or sorted(s for s in instruments() if (args.store / s).is_dir())
    frames = {s: research_frames.load(s, min(START_2012, WARM_UP), holdout, args.store)
              for s in symbols}  # fmt: skip
    results, book, draws = evaluate(frames, load_swaps(SWAPS), deltas_, seeds_, REPS, BOOT)
    args.out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (args.out / f"eval_{r.name}.md").write_text(
            strategy_report(r, commit, head, seeds_, BOOT, REPS), encoding="utf-8", newline="\n"
        )
    run_date = pd.Timestamp.now(tz="UTC").date().isoformat()
    (args.out / "evaluation.md").write_text(
        summary_report(results, commit, head, run_date), encoding="utf-8", newline="\n"
    )
    book.to_parquet(args.store / "stage_c_trades.parquet", index=False)
    pd.DataFrame(draws).to_parquet(args.store / "stage_c_e0.parquet", index=False)
    print(f"wrote {args.out / 'evaluation.md'} and {len(results)} strategy reports")
    return 0
