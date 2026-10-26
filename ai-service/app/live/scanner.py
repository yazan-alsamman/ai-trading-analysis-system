"""The live scanner (P6 task 3): every setup in a request's window and its lifecycle so far.

It runs the research code unchanged on the frames of ``app.live.frames``: ``detect`` (L2),
``build`` (L3) and ``resolve`` (the lifecycle and triple barrier of ``app.setups.labels``). The
same bars therefore give the same setups, states and realised R as the research pipeline
(``label_all``), which P6 task 5 checks bar by bar.

Lifecycle in contract states, with the time each change became known (a bar's close):

* ``ARMED`` at the close of the decision (CHoCH) bar, ``created_at``;
* ``ACTIVE``: L1 enters at market at that close, so at the same time;
* ``CLOSED`` at the close of the exit bar, with ``reason`` ``tp``, ``sl`` or ``timeout`` and the
  net realised R (after the cost model). An active trade never becomes ``INVALIDATED`` in L1.

Not yet: ``DEVELOPING`` (a sweep waiting for its CHoCH), and the limit-entry rule sets (V5-S)
and position management (L1-M); only the ``intraday`` profile (L1) is served.

``horizon_until`` is an estimate: the horizon is counted in entry bars, so its time is the close
of the ``horizon_bars``-th entry slot inside trading hours (``app.data.sessions.is_open``); a
holiday or a gap in the feed moves the real end later."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.config import Instrument, Strategy
from app.contract import SetupState
from app.data.sessions import is_open
from app.setups.builder import Setup, build
from app.setups.labels import Bars, Label, resolve
from app.smc.detector import detect


@dataclass(frozen=True)
class Step:
    state: SetupState
    at: pd.Timestamp
    reason: str | None = None
    realized_r: float | None = None


@dataclass(frozen=True)
class LiveSetup:
    setup: Setup
    label: Label
    created_at: pd.Timestamp
    valid_until: pd.Timestamp
    horizon_until: pd.Timestamp
    path: tuple[Step, ...]  # oldest first; the last step is the state as of the request
    rejected: bool = False  # the builder rejected the pattern (no trade plan)

    @property
    def state(self) -> SetupState:
        return self.path[-1].state


def supported(p: Strategy) -> None:
    if p.entry_mode != "close" or p.management != "none":
        raise NotImplementedError(
            f"live evaluation serves market-entry rule sets, not {p.rule_set}"
        )


def slots_after(t: pd.Timestamp, n: int, step: pd.Timedelta, inst: Instrument) -> pd.Timestamp:
    """The close of the ``n``-th ``step`` slot inside trading hours that opens at or after
    ``t``."""
    found, start = 0, t
    while True:
        grid = pd.date_range(start, periods=4 * n + 8, freq=step)
        open_ = grid[is_open(grid, inst)]
        if found + len(open_) >= n:
            return open_[n - found - 1] + step
        found += len(open_)
        start = grid[-1] + step


def scan(frames: dict[str, pd.DataFrame], p: Strategy, inst: Instrument) -> list[LiveSetup]:
    """Every pattern whose decision bar is in the window, with its lifecycle as of the close of
    the last entry bar. Rejected patterns are kept (``rejected``) for the abstentions."""
    supported(p)
    entry = frames[p.entry_timeframe]
    step = entry["close_utc"].iloc[0] - entry["ts_utc"].iloc[0]
    close_utc = entry["close_utc"]
    sides = {d: Bars.of(entry, d) for d in ("buy", "sell")}
    out = []
    for st in build(frames, detect(frames, p), p):
        created = close_utc.iloc[st.decision_idx]
        valid_until = created + step  # a market entry: the price of the decision close
        horizon = slots_after(created, p.horizon_bars, step, inst)
        if st.plan.state != "ARMED":
            lab = Label("REJECTED", st.plan.reason)
            out.append(LiveSetup(st, lab, created, valid_until, horizon, (), rejected=True))
            continue
        lab = resolve(sides[st.pattern.direction], st.decision_idx, st.plan, st.spread, p, inst)
        path = [Step(SetupState.ARMED, created), Step(SetupState.ACTIVE, created)]
        if lab.state == "CLOSED":
            path.append(
                Step(SetupState.CLOSED, close_utc.iloc[lab.exit_idx], lab.reason, lab.net_r)
            )
        elif lab.state != "PENDING":
            raise AssertionError(f"unexpected lifecycle {lab.state} for a market entry")
        out.append(LiveSetup(st, lab, created, valid_until, horizon, tuple(path)))
    return out
