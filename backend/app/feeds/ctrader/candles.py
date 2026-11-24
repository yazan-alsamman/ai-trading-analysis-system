"""1-minute bars from spot quotes (B1, docs/ctrader-feed.md#candles). Pure: no I/O.

- **Bid basis.** OHLC are built on the **bid**, the instrument's ``price_basis`` (FxPro charts
  show bid). A quote that only changes the ask updates the spread, not the OHLC.
- **Spread, time-weighted.** ``ask - bid`` in price units, averaged over the minute weighted by
  how long each quote stood: from the first quote of the minute to the minute's end, each
  quote counts until the next one (the last one until the minute's end). The time before the
  minute's first quote is not counted (it belongs to the previous minute's quotes).
- **Volume = tick count.** cTrader spot events carry no traded volume; ``volume`` is the
  number of quotes (spot events) in the minute, ``trades`` stays null.
- **Close.** A bar is closed by the first quote of a later minute, or by the timer at the
  minute's end + ``grace`` seconds when no quote comes. A minute without any quote has no bar
  (weekends, the daily break).
- Minutes are UTC (``ts`` = the minute's start).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

MINUTE = timedelta(minutes=1)


def minute_of(ts: datetime) -> datetime:
    ts = ts.astimezone(UTC)
    return ts.replace(second=0, microsecond=0)


@dataclass
class Bar:
    ts: datetime  # the minute's start (UTC)
    open: float
    high: float
    low: float
    close: float
    ticks: int = 0
    spread_weighted: float = 0.0  # sum of spread x seconds
    spread_seconds: float = 0.0
    last_quote_at: datetime | None = None
    last_spread: float | None = None
    spread_sum: float = 0.0  # plain sum and count: the fallback when no time passed
    spread_count: int = 0

    @property
    def end(self) -> datetime:
        return self.ts + MINUTE

    def _settle(self, until: datetime) -> None:
        """Weigh the standing spread up to ``until`` (capped at the minute's end)."""
        if self.last_quote_at is None or self.last_spread is None:
            return
        until = min(until, self.end)
        seconds = (until - self.last_quote_at).total_seconds()
        if seconds > 0:
            self.spread_weighted += self.last_spread * seconds
            self.spread_seconds += seconds
            self.last_quote_at = until

    @property
    def spread(self) -> float | None:
        """The time-weighted mean spread; when every quote came at the same instant (no time
        to weigh), their plain mean."""
        if self.spread_seconds > 0:
            return self.spread_weighted / self.spread_seconds
        return self.spread_sum / self.spread_count if self.spread_count else None


@dataclass(frozen=True)
class ClosedBar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int  # tick count
    spread: float | None


class BarBuilder:
    """Feed it quotes in time order (``quote``) and call ``due`` from a timer; both return the
    bars that closed. ``digits`` rounds the spread to the symbol's price precision + 2."""

    def __init__(self, grace_seconds: float = 3.0, digits: int | None = None) -> None:
        self.grace = timedelta(seconds=grace_seconds)
        self.digits = digits
        self.bid: float | None = None
        self.ask: float | None = None
        self.current: Bar | None = None
        self.closed_until: datetime | None = None  # the end of the last closed bar

    def quote(
        self, at: datetime, bid: float | None = None, ask: float | None = None
    ) -> list[ClosedBar]:
        """One spot event at ``at``: either price may be missing (the event only carries what
        changed). Returns the bar closed by it (a quote of a later minute), if any."""
        closed: list[ClosedBar] = []
        at = at.astimezone(UTC)
        if self.current is not None and at >= self.current.end:
            closed.append(self._close())
        if self.closed_until is not None and at < self.closed_until:
            return closed  # late: its minute is closed already (ignored)
        if self.current is not None and at < self.current.ts:
            return closed  # out of order (ignored)
        if bid is not None:
            self.bid = bid
        if ask is not None:
            self.ask = ask
        if self.bid is None:
            return closed  # nothing to build a bid bar from yet
        bar = self.current
        if bar is None:
            bar = self.current = Bar(minute_of(at), self.bid, self.bid, self.bid, self.bid)
        bar._settle(at)
        if bid is not None:
            bar.high = max(bar.high, self.bid)
            bar.low = min(bar.low, self.bid)
            bar.close = self.bid
        bar.ticks += 1
        if self.ask is not None:
            spread = max(0.0, self.ask - self.bid)
            bar.last_spread, bar.last_quote_at = spread, at
            bar.spread_sum += spread
            bar.spread_count += 1
        return closed

    def due(self, now: datetime) -> list[ClosedBar]:
        """The timer: close the open bar once ``now`` is past its end + the grace."""
        if self.current is not None and now.astimezone(UTC) >= self.current.end + self.grace:
            return [self._close()]
        return []

    def _close(self) -> ClosedBar:
        bar = self.current
        assert bar is not None
        bar._settle(bar.end)
        self.current = None
        self.closed_until = bar.end
        spread = bar.spread
        if spread is not None and self.digits is not None:
            spread = round(spread, self.digits + 2)
        return ClosedBar(bar.ts, bar.open, bar.high, bar.low, bar.close, bar.ticks, spread)
