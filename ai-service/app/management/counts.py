"""Post-approval counts (docs/strategies/PREREG.md, section 12): after approval, before Stage C, on
the primary period only, with bars loaded only to the holdout start (2024-07-01).

Per strategy, instrument and year, for armed candidates with entry in the primary period (earlier
bars are indicator warm-up only):

* under M0's one-active-trade rule (the family A trades): trades, resolved and unresolved, and
  candidates rejected as ``position_open`` or left undecided after an unresolved trade;
* under the served-signal rules (one active trade per strategy and instrument, and the conflict
  rule across strategies on the instrument: a signal opposite to an active served trade of
  another strategy is ``conflict`` and not served; the first signal wins, ties by strategy name):
  served, ``position_open``, ``conflict`` and undecided. Exposure limits are not agreed yet.

Per strategy: n (resolved family A trades), K, sigma = sqrt(mean k) of their R multiples, DE, MDE
at alpha/m and alpha, delta*_S (from the pre-approval counts) and n_unval (section 8).

Exits are used inside the computation only, to know which later candidate a trade blocks; no R,
exit reason, exit price or exit time is returned, written or printed (``check_no_outcomes``).
Refused: a bar after the holdout start, and ``run`` before the preregistration is approved."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import (
    Bundle,
    Instrument,
    Rules,
    SignalSpec,
    bundles,
    instruments,
    rules,
    signal_specs,
)
from app.data.importer import DEFAULT_OUT as STORE
from app.management.book import manager, one_active
from app.management.engine import Outcome
from app.research.decide import ALPHA, block_ids, mde, n_unval
from app.strategies import frames as research_frames
from app.strategies.base import Candidate
from app.strategies.counts import bounds, check_no_outcomes
from app.strategies.rules import Frames, candidates

PREREG = Path(__file__).resolve().parents[2] / "docs" / "strategies" / "PREREG.md"
WARM_UP = pd.Timestamp("2017-01-01", tz="UTC")
# Design effect for the power statements (section 8): provisional assumptions, not measured.
DE = {"S4": 1.5, "S8": 1.5}
DE_DEFAULT = 1.2


def approved(prereg: Path = PREREG) -> bool:
    """True once the approval date of the preregistration's table is filled in."""
    m = re.search(r"^\| Approval date \| (.+?) \|$", prereg.read_text(encoding="utf-8"), re.M)
    return bool(m) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", m.group(1).strip()) is not None


def serve(
    armed: list[tuple[Candidate, int]], manage: dict[str, Callable[[Candidate], Outcome]]
) -> list[tuple[Candidate, str]]:
    """The served-signal rules on one instrument. ``armed`` holds every strategy's armed
    candidates with their entry time (ns). Returns each with ``served``, ``position_open``,
    ``conflict`` or ``undecided`` (after an unresolved served trade of its strategy)."""
    order = sorted(armed, key=lambda x: (x[1], x[0].strategy, x[0].idx, x[0].direction))
    flat_from: dict[str, int] = {}
    blocked: set[str] = set()
    live: list[tuple[str, str, int | None]] = []  # strategy, direction, exit (None: unresolved)
    out = []
    for c, t in order:
        s = c.strategy
        live = [x for x in live if x[2] is None or t < x[2]]
        if s in blocked:
            out.append((c, "undecided"))
        elif c.idx < flat_from.get(s, -1):
            out.append((c, "position_open"))
        elif any(x[0] != s and x[1] != c.direction for x in live):
            out.append((c, "conflict"))
        else:
            o = manage[s](c)
            out.append((c, "served"))
            if o.state == "CLOSED":
                flat_from[s] = o.exit_idx
                live.append((s, c.direction, o.exit_ns))
            else:
                blocked.add(s)
                live.append((s, c.direction, None))
    return out


def _memo(run: Callable[[Candidate], Outcome]) -> Callable[[Candidate], Outcome]:
    seen: dict[tuple[int, str], Outcome] = {}

    def f(c: Candidate) -> Outcome:
        key = (c.idx, c.direction)
        if key not in seen:
            seen[key] = run(c)
        return seen[key]

    return f


def instrument_rows(
    frames: Frames, inst: Instrument, specs: Iterable[SignalSpec], rp: Rules, m0: Bundle
) -> pd.DataFrame:
    """One row per armed candidate of the primary period: its family A state (``resolved``,
    ``unresolved``, ``position_open``, ``undecided``) and its served state. No outcome."""
    primary, holdout, _ = bounds()
    for tf, f in frames.items():
        if len(f) and f["close_utc"].max() > holdout:
            raise ValueError(f"{inst.symbol} {tf}: bars after the holdout start {holdout}")
    rows, armed, runs = [], [], {}
    for spec in specs:
        close = frames[spec.frame]["close_utc"]
        cs = [
            c for c in candidates(frames, inst, spec)
            if c.state == "ARMED" and close.iloc[c.idx] >= primary
        ]  # fmt: skip
        runs[spec.name] = _memo(manager(frames, inst, spec, rp, m0))
        for c, o in one_active(cs, runs[spec.name]):
            if o is not None:
                state = "resolved" if o.state == "CLOSED" else "unresolved"
            else:
                state = "position_open" if c.reason == "position_open" else "undecided"
            t = close.iloc[c.idx]
            rows.append(
                {
                    "strategy": spec.name,
                    "idx": c.idx,
                    "direction": c.direction,
                    "entry_utc": t,
                    "k": c.r_multiple,
                    "family_a": state,
                }  # fmt: skip
            )
            armed.append((replace(c, state="ARMED", reason=""), t.value))
    served = {(c.strategy, c.idx, c.direction): s for c, s in serve(armed, runs)}
    out = pd.DataFrame(rows, columns=["strategy", "idx", "direction", "entry_utc", "k", "family_a"])
    keys = zip(out["strategy"], out["idx"], out["direction"], strict=True)
    out["served"] = [served[k] for k in keys]
    out["symbol"] = inst.symbol
    return out


def report(
    rows: pd.DataFrame, specs: Iterable[SignalSpec], deltas: dict[str, float] | None = None
) -> dict[str, pd.DataFrame]:
    """``by_year`` (strategy x instrument x year) and ``power`` (per strategy)."""
    specs = list(specs)
    rows = rows.assign(year=pd.DatetimeIndex(rows["entry_utc"]).year)
    by_year = []
    for (name, symbol, year), g in rows.groupby(["strategy", "symbol", "year"]):
        a, s = g["family_a"], g["served"]
        by_year.append(
            {
                "strategy": name,
                "symbol": symbol,
                "year": int(year),
                "armed": len(g),
                "trades": int(a.isin(["resolved", "unresolved"]).sum()),
                "resolved": int((a == "resolved").sum()),
                "unresolved": int((a == "unresolved").sum()),
                "position_open": int((a == "position_open").sum()),
                "undecided": int((a == "undecided").sum()),
                "served": int((s == "served").sum()),
                "served_position_open": int((s == "position_open").sum()),
                "conflict": int((s == "conflict").sum()),
                "served_undecided": int((s == "undecided").sum()),
            }  # fmt: skip
        )
    power = []
    for sp in specs:
        m = sum(x.family == sp.family for x in specs)
        g = rows[(rows["strategy"] == sp.name) & (rows["family_a"] == "resolved")]
        n = len(g)
        sigma = float(np.sqrt(g["k"].mean())) if n else np.nan
        de = DE.get(sp.name, DE_DEFAULT)
        delta = (deltas or {}).get(sp.name, np.nan)
        known = n > 0 and not np.isnan(delta)
        power.append(
            {
                "strategy": sp.name,
                "family": sp.family,
                "n": n,
                "K": len(np.unique(block_ids(g["entry_utc"]))) if n else 0,
                "sigma": sigma,
                "DE": de,
                "mde_alpha_m": mde(n, sigma, de, ALPHA / m) if n else np.nan,
                "mde_alpha": mde(n, sigma, de, ALPHA) if n else np.nan,
                "delta_star": delta,
                "n_unval": n_unval(delta, sigma, de) if known else np.nan,
            }  # fmt: skip
        )
    tables = {"by_year": pd.DataFrame(by_year), "power": pd.DataFrame(power)}
    return {k: check_no_outcomes(v) for k, v in tables.items()}


def counts(
    frames_by_symbol: dict[str, Frames], deltas: dict[str, float] | None = None
) -> dict[str, pd.DataFrame]:
    specs = list(signal_specs().values())
    rp, m0 = rules(), bundles()["M0"]
    rows = [
        instrument_rows(f, instruments()[s], specs, rp, m0) for s, f in frames_by_symbol.items()
    ]
    return report(pd.concat(rows, ignore_index=True), specs, deltas)


def run(
    symbols: Iterable[str], store: Path = STORE, deltas: dict[str, float] | None = None
) -> dict[str, pd.DataFrame]:
    """The post-approval counts from the store. Refused while the preregistration is a draft."""
    if not approved():
        raise PermissionError("post-approval counts need the approved preregistration")
    _, holdout, _ = bounds()
    return counts({s: research_frames.load(s, WARM_UP, holdout, store) for s in symbols}, deltas)
