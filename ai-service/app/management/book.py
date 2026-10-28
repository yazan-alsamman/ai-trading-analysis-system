"""One active trade per strategy and instrument (docs/strategies/PREREG.md, section 3), and the
fixed entry set of family C (section 9).

Candidates are taken in signal order. An armed candidate whose signal bar comes before the exit
bar of the open trade is rejected (``position_open``); one at or after it opens a new trade (an
exit at a bar's open or inside it leaves the position flat at that bar's close). A trade that
cannot be decided yet (``PENDING``) ends the run: nothing after it can be decided, and those
candidates come back with no outcome.

**Fixed entry set (family C).** The entries are the trades of M0's one-active-trade rule. Every
bundle manages each of those entries on its own, so each bundle has its own exit time, exit reason
and net R per entry (``fixed_entry_table``); no bundle's columns are derived from another's. Under
a bundle that exits later than M0 two managed trades of one strategy can overlap in time
(``overlaps``), and under a bundle's own one-active rule the entry set would differ
(``entry_set_difference``). Both are descriptive diagnostics of the approximation: they decide
nothing and are not portfolio results."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np
import pandas as pd

from app.config import Bundle, Instrument, Rules, SignalSpec
from app.management.engine import Market, Outcome, manage
from app.research.decide import exit_col, r_col
from app.strategies import swap
from app.strategies.base import Candidate
from app.strategies.rules import STRATEGIES, Frames, candidates, thesis


def one_active(
    cands: list[Candidate], manage: Callable[[Candidate], Outcome]
) -> list[tuple[Candidate, Outcome | None]]:
    out: list[tuple[Candidate, Outcome | None]] = []
    flat_from = -1
    ordered = sorted(cands, key=lambda c: (c.idx, c.direction))
    for i, c in enumerate(ordered):
        if c.state != "ARMED":
            out.append((c, None))
            continue
        if c.idx < flat_from:
            out.append((replace(c, state="REJECTED", reason="position_open"), None))
            continue
        res = manage(c)
        out.append((c, res))
        if res.state != "CLOSED":
            out.extend((x, None) for x in ordered[i + 1 :])
            break
        flat_from = res.exit_idx
    return out


def manager(
    frames: Frames, inst: Instrument, spec: SignalSpec, rp: Rules, bundle: Bundle
) -> Callable[[Candidate], Outcome]:
    """``manage`` of one strategy's candidates under ``bundle`` on these frames."""
    e = frames[spec.frame]
    l5 = STRATEGIES[spec.name][1]
    th = thesis(frames, spec, rp.L5_adx_max) if "L5" in bundle.rules else None
    markets: dict[str, Market] = {}

    def run(c: Candidate) -> Outcome:
        if c.direction not in markets:
            markets[c.direction] = Market.of(e, c.direction, spec.frame, rp)
        series = th[c.direction] if th else None
        return manage(markets[c.direction], c, bundle, rp, inst, l5, series)

    return run


def fixed_entry_table(
    frames: Frames,
    inst: Instrument,
    spec: SignalSpec,
    rp: Rules,
    bundles: dict[str, Bundle],
    swap_spec: swap.SwapSpec | None = None,
) -> pd.DataFrame:
    """One row per entry of M0's one-active-trade rule: ``entry_utc`` (the signal bar's close)
    and, per bundle b, ``exit_utc_<b>``, ``reason_<b>`` and ``net_r_<b>`` from b's own management
    of the entry (NaT / NaN while unresolved). Net R includes the W1 swap when ``swap_spec`` is
    given, by the bundle's own exit time, at the price of each rollover (``swap.close_before``)."""
    e = frames[spec.frame]
    cands = candidates(frames, inst, spec)
    first = one_active(cands, manager(frames, inst, spec, rp, bundles["M0"]))
    entries = [c for c, o in first if o is not None]
    entry_utc = [e["close_utc"].iloc[c.idx] for c in entries]
    price_at = swap.close_before(e)
    out = pd.DataFrame(
        {
            "symbol": inst.symbol,
            "strategy": spec.name,
            "idx": [c.idx for c in entries],
            "direction": [c.direction for c in entries],
            "entry_utc": pd.to_datetime(entry_utc, utc=True),
        }
    )
    for name, b in bundles.items():
        run = manager(frames, inst, spec, rp, b)
        exits, reasons, net = [], [], []
        for c, t in zip(entries, entry_utc, strict=True):
            o = run(c)
            if o.state != "CLOSED":
                exits.append(pd.NaT), reasons.append(""), net.append(np.nan)
                continue
            x = pd.Timestamp(o.exit_ns, tz="UTC")
            w1 = 0.0
            if swap_spec is not None:
                w1 = swap.swap_r(swap_spec, c.direction, t, x, c.risk, c.entry, price_at)
            exits.append(x), reasons.append(o.reason), net.append(o.net_r() + w1)
        out[exit_col(name)] = pd.to_datetime(exits, utc=True)
        out[f"reason_{name}"] = reasons
        out[r_col(name)] = net
    return out


def overlaps(table: pd.DataFrame, bundle: str) -> int:
    """Entries of the fixed set that start while an earlier entry of the same strategy and
    instrument is still open under ``bundle`` (an unresolved one counts as open)."""
    n = 0
    for _, g in table.sort_values("entry_utc").groupby(["symbol", "strategy"]):
        open_until = None
        for t, x in zip(g["entry_utc"], g[exit_col(bundle)], strict=True):
            if open_until is not None and (pd.isna(open_until) or t < open_until):
                n += 1
            if open_until is None or pd.isna(x) or (not pd.isna(open_until) and x > open_until):
                open_until = x
    return n


def entry_set_difference(
    frames: Frames, inst: Instrument, spec: SignalSpec, rp: Rules, bundles: dict[str, Bundle]
) -> dict[str, tuple[int, int]]:
    """Per bundle: (entries its own one-active rule would add, entries it would drop), against
    M0's fixed entry set."""

    def entry_set(b: Bundle) -> set[tuple[int, str]]:
        got = one_active(cands, manager(frames, inst, spec, rp, b))
        return {(c.idx, c.direction) for c, o in got if o is not None}

    cands = candidates(frames, inst, spec)
    m0 = entry_set(bundles["M0"])
    out = {}
    for name, b in bundles.items():
        own = m0 if name == "M0" else entry_set(b)
        out[name] = (len(own - m0), len(m0 - own))
    return out
