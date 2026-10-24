"""The ai-service contract (B7, docs/ai-contract.md): requests the backend sends and responses
it accepts on ``POST /v1/evaluate``, ``/v1/size`` and ``/v1/explain``.

Version 0.2.0 (``CONTRACT_VERSION``): Fadi's answers to the 17 open points of 0.1.0-draft are
applied (docs/ai-contract.md section 7). ``/v1`` only ever gains fields; the version follows
semver. The generated document is docs/api/ai-service.openapi.yaml (``scripts/ai_contract.py``);
example payloads are in docs/api/ai-service-examples/.

Depends on pydantic only, so ai-service can vendor this file as it is.

- Requests (built by us) forbid unknown fields; responses (built by ai-service) ignore them,
  so ai-service can add fields without breaking us.
- ``Setup`` is ai-service's object: it keeps unknown fields both ways, and a setup parsed from
  JSON serialises back to exactly that JSON (``open_setups`` echoes setups as last returned).
- Timestamps are timezone-aware and normalised to UTC (``...Z`` on the wire); prices are
  finite and positive; ``0 <= probability <= 1``.
- ``1d`` bars are trading days of 17:00 to 17:00 America/New_York (DST-aware), not UTC days:
  ``bar_close`` gives the close of a bar of any timeframe.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    ValidatorFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from pydantic_core import to_jsonable_python

CONTRACT_VERSION = "0.2.0"


# --- shared types -------------------------------------------------------------------------------


class SetupState(StrEnum):
    DEVELOPING = "DEVELOPING"
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


FINAL_STATES = frozenset({SetupState.CLOSED, SetupState.EXPIRED, SetupState.INVALIDATED})
PRICED_STATES = frozenset({SetupState.ARMED, SetupState.ACTIVE})
# The order of the life cycle (Fadi, points 9 and 10): a state never goes backwards. The final
# states share the last rank.
STATE_RANK: dict[SetupState, int] = {
    SetupState.DEVELOPING: 0,
    SetupState.ARMED: 1,
    SetupState.ACTIVE: 2,
    SetupState.CLOSED: 3,
    SetupState.EXPIRED: 3,
    SetupState.INVALIDATED: 3,
}
# The only state changes (Fadi, point 9): DEVELOPING -> ARMED -> ACTIVE -> CLOSED, and
# DEVELOPING or ARMED -> EXPIRED or INVALIDATED. No DEVELOPING -> ACTIVE (ARMED and ACTIVE may
# come in the same response with the same ``at``), and no ACTIVE -> INVALIDATED.
ALLOWED_TRANSITIONS: dict[SetupState, frozenset[SetupState]] = {
    SetupState.DEVELOPING: frozenset(
        {SetupState.ARMED, SetupState.EXPIRED, SetupState.INVALIDATED}
    ),
    SetupState.ARMED: frozenset({SetupState.ACTIVE, SetupState.EXPIRED, SetupState.INVALIDATED}),
    SetupState.ACTIVE: frozenset({SetupState.CLOSED}),
}


class Direction(StrEnum):
    buy = "buy"
    sell = "sell"


class EvaluateStatus(StrEnum):
    ok = "ok"
    data_quality_failed = "data_quality_failed"
    model_unavailable = "model_unavailable"


class Grade(StrEnum):
    """A best .. D worst (Fadi, point 1). **Always null in v1**: no model has passed the gate
    yet, so every reader (API, UI, alerts) must handle a null grade."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


TIMEFRAMES: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}
Timeframe = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]


NEW_YORK = ZoneInfo("America/New_York")
DAY_CLOSE_HOUR = 17  # the trading day ends at 17:00 New York time (Fadi, point 5)


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _ny_at_close(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, DAY_CLOSE_HOUR, tzinfo=NEW_YORK).astimezone(UTC)


def d1_open(value: datetime) -> datetime:
    """Open (UTC) of the trading day containing ``value``: the latest 17:00 America/New_York
    at or before it. 22:00 UTC in winter (EST), 21:00 UTC in summer (EDT)."""
    local = value.astimezone(NEW_YORK)
    start = _ny_at_close(local.year, local.month, local.day)
    if start > value.astimezone(UTC):
        before = local.date() - timedelta(days=1)
        start = _ny_at_close(before.year, before.month, before.day)
    return start


def d1_close(open_ts: datetime) -> datetime:
    """Close (UTC) of the trading day opening at ``open_ts``: 17:00 New York the next day
    (23 or 25 hours later across a DST change)."""
    after = open_ts.astimezone(NEW_YORK).date() + timedelta(days=1)
    return _ny_at_close(after.year, after.month, after.day)


def bar_close(timeframe: str, ts: datetime) -> datetime:
    """When the bar of ``timeframe`` opening at ``ts`` closes: ``ts`` + the timeframe, except
    ``1d`` (17:00 New York the next day)."""
    if timeframe == "1d":
        return d1_close(ts)
    return ts + TIMEFRAMES[timeframe]


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_utc)]
Price = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Instrument = Annotated[str, Field(pattern=r"^[A-Z0-9]{3,16}$", examples=["XAUUSD"])]
Profile = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,32}$", examples=["intraday"])]
SetupId = Annotated[str, Field(min_length=1, max_length=128)]


def iso_z(value: datetime) -> str:
    """``2026-10-19T14:15:00Z`` (the wire format of every timestamp)."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def make_request_id(instrument: str, profile: str, bar_close_ts: datetime) -> str:
    """Deterministic: the same instrument, profile and bar always give the same id."""
    return f"{instrument.lower()}-{profile}-{iso_z(bar_close_ts)}"


class _Request(BaseModel):
    """What we build: unknown fields are a bug."""

    model_config = ConfigDict(extra="forbid")


class _Response(BaseModel):
    """What ai-service builds: unknown fields are ignored (it may add fields)."""

    model_config = ConfigDict(extra="ignore")


# --- evaluate -----------------------------------------------------------------------------------


class Bar(_Request):
    """One **closed** bar. ``ts`` is the bar's open time (UTC); it closes at ``ts`` + timeframe."""

    ts: UtcDatetime
    o: Price
    h: Price
    l: Price  # noqa: E741 - the contract's name
    c: Price
    spread: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = Field(
        default=None,
        description="average spread over the bar, in price units (XAU/USD 0.25). The decision "
        "bar (the last bar of the smallest timeframe) always has one: without it the backend "
        "does not call ai-service",
    )

    @model_validator(mode="after")
    def _ohlc(self) -> Self:
        if self.h < max(self.o, self.c, self.l) or self.l > min(self.o, self.c):
            raise ValueError("inconsistent OHLC (h must be the highest, l the lowest)")
        return self


class CalendarEvent(_Request):
    """An economic-calendar event (B6 ``for_evaluate``)."""

    ts: UtcDatetime
    currency: Annotated[str, Field(pattern=r"^[A-Z]{2,8}$", examples=["USD"])]
    impact: Literal["high", "medium", "low", "holiday"]
    title: Annotated[str, Field(min_length=1, max_length=255)]


class InstrumentSpec(_Request):
    """Contract specs (B4, docs/instruments.md), sent with every evaluate and size request
    (Fadi, point 2). Prices are rounded to ``tick_size``: the stop **away from** the entry, the
    target **toward** it (the backend uses the same rule wherever it rounds a price)."""

    contract_size: Price = Field(description="units per 1.0 lot (XAU/USD: 100 oz)")
    tick_size: Price = Field(description="minimum price increment (XAU/USD: 0.01)")
    lot_step: Price
    min_lot: Price
    max_lot: Price
    price_basis: Literal["bid", "mid", "last"] = Field(description="the price the bars use")
    session_calendar: dict[str, Any] | None = Field(
        default=None,
        description="when the market trades (docs/instruments.md#session-calendar); null: 24/7",
    )
    quote_currency: Annotated[str, Field(pattern=r"^[A-Z0-9]{2,16}$")] | None = Field(
        default=None, description="currency of the P&L per price unit (XAU/USD: USD)"
    )
    margin_rate: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] | None = Field(
        default=None,
        description="margin as a fraction of notional; margin = notional in USD x "
        "max(margin_rate, 1 / leverage); null: 1 / leverage",
    )

    @model_validator(mode="after")
    def _lots(self) -> Self:
        if self.min_lot > self.max_lot:
            raise ValueError("min_lot must be <= max_lot")
        return self


class Setup(BaseModel):
    """A trade setup as ai-service returns it. ``setup_id`` is deterministic (ai-service).

    Unknown fields are kept, and a setup parsed from JSON serialises back to that exact JSON,
    so ``open_setups`` echoes it unchanged. In ``ARMED`` and ``ACTIVE``, ``entry``, ``sl`` and
    ``tp`` are required and on the right side: buy ``sl < entry < tp``, sell ``tp < entry < sl``.
    """

    model_config = ConfigDict(extra="allow")
    _raw: dict[str, Any] | None = PrivateAttr(default=None)

    setup_id: SetupId
    state: SetupState
    direction: Direction
    entry: Price | None = None
    sl: Price | None = None
    tp: Price | None = None
    r_multiple: Finite | None = Field(default=None, description="reward / risk at entry")
    probability: Probability | None = Field(default=None, description="of reaching tp first")
    ev_r: Finite | None = Field(default=None, description="expected value in R")
    ev_r_lower: Finite | None = Field(default=None, description="lower bound of ev_r")
    grade: Grade | None = Field(default=None, description="A best .. D; always null in v1")
    valid_until: UtcDatetime | None = Field(default=None, description="entry no longer valid")
    horizon_until: UtcDatetime | None = Field(default=None, description="trade horizon end")
    created_at: UtcDatetime | None = Field(
        default=None,
        description="close of the bar where the setup became known as DEVELOPING (the time of "
        "its first event); optional until ai-service sends it",
    )
    evidence: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="wrap")
    @classmethod
    def _keep_raw(cls, data: Any, handler: ValidatorFunctionWrapHandler) -> Setup:
        setup = handler(data)
        if isinstance(data, dict):
            # JSON input is kept as it is; Python objects (datetimes, enums) become JSON
            setup._raw = to_jsonable_python(data)
        return setup

    @model_validator(mode="after")
    def _prices(self) -> Self:
        if self.state not in PRICED_STATES:
            return self
        if self.entry is None or self.sl is None or self.tp is None:
            raise ValueError(f"a {self.state.value} setup needs entry, sl and tp")
        if self.direction == Direction.buy and not self.sl < self.entry < self.tp:
            raise ValueError("buy: sl < entry < tp")
        if self.direction == Direction.sell and not self.tp < self.entry < self.sl:
            raise ValueError("sell: tp < entry < sl")
        return self

    @model_serializer(mode="wrap")
    def _echo(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        if self._raw is not None:
            return copy.deepcopy(self._raw)
        return handler(self)

    def payload(self) -> dict[str, Any]:
        """The setup as JSON (exactly as received when it was parsed from JSON)."""
        return self.model_dump(mode="json")


class EvaluateRequest(_Request):
    """Evaluate the bar that closed at ``bar_close_ts``. Every bar is closed; the smallest
    timeframe ends exactly at ``bar_close_ts`` (its last bar is the one just closed, the
    decision bar, which has a spread). ``1d`` bars open at 17:00 America/New_York."""

    request_id: str = Field(
        max_length=160,
        description="deterministic: {instrument lower}-{profile}-{bar_close_ts}",
        examples=["xauusd-intraday-2026-10-19T14:15:00Z"],
    )
    instrument: Instrument
    profile: Profile
    bar_close_ts: UtcDatetime
    bars: dict[Timeframe, Annotated[list[Bar], Field(min_length=1, max_length=5000)]] = Field(
        description="timeframe -> bars, oldest first (defaults: 2000 x 15m, 500 x 1h, "
        "300 x 4h, 260 x 1d; fewer when the history is shorter)"
    )
    open_setups: list[Setup] = Field(
        default_factory=list,
        max_length=200,
        description="every non-final setup of this instrument and profile, exactly as last "
        "returned",
    )
    calendar: list[CalendarEvent] = Field(default_factory=list, max_length=500)
    instrument_spec: InstrumentSpec

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        expected = make_request_id(self.instrument, self.profile, self.bar_close_ts)
        if self.request_id != expected:
            raise ValueError(f"request_id must be {expected!r}")
        if not self.bars:
            raise ValueError("bars needs at least one timeframe")
        for tf, bars in self.bars.items():
            for before, after in zip(bars, bars[1:], strict=False):
                if after.ts <= before.ts:
                    raise ValueError(f"bars[{tf}] must be oldest first, without duplicates")
            if tf == "1d" and any(d1_open(b.ts) != b.ts for b in bars):
                raise ValueError("bars[1d] must open at 17:00 America/New_York")
            if bar_close(tf, bars[-1].ts) > self.bar_close_ts:
                raise ValueError(f"bars[{tf}]: the last bar is not closed at bar_close_ts")
        smallest = min(self.bars, key=lambda tf: TIMEFRAMES[tf])
        if bar_close(smallest, self.bars[smallest][-1].ts) != self.bar_close_ts:
            raise ValueError(f"bars[{smallest}] must end with the bar closing at bar_close_ts")
        return self


class Versions(_Response):
    """Always present: ``strategy`` and ``features``. ``model`` is null only with
    ``model_unavailable`` (Fadi, point 12)."""

    strategy: str = Field(max_length=64)
    model: str | None = Field(
        default=None, max_length=128, description="null only with status model_unavailable"
    )
    features: str = Field(max_length=64)


class Transition(_Response):
    """A state change of an existing setup, decided by ai-service."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, serialize_by_alias=True)

    setup_id: SetupId
    from_: SetupState = Field(alias="from")
    to: SetupState
    at: UtcDatetime
    reason: str | None = Field(default=None, max_length=255)
    realized_r: Finite | None = Field(default=None, description="set when it closes")


class Abstention(_Response):
    reason: str = Field(max_length=64, examples=["high_impact_event"])
    detail: dict[str, Any] = Field(default_factory=dict, description="an object (Fadi, point 14)")


class EvaluateResponse(_Response):
    """``new_setups`` carries the **current state** of every setup ai-service knows about, and
    ``transitions`` the **full history** of their state changes (Fadi, point 10): the backend
    dedupes by ``(setup_id, to, at)``. The same body gives a byte-identical response (point
    16). ``status`` ``model_unavailable`` is a 200, not a 503 (point 8)."""

    request_id: str
    status: EvaluateStatus
    versions: Versions
    new_setups: list[Setup] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    abstentions: list[Abstention] = Field(default_factory=list)

    @model_validator(mode="after")
    def _model(self) -> Self:
        if self.status == EvaluateStatus.ok and self.versions.model is None:
            raise ValueError("versions.model is null only with status model_unavailable")
        return self


# --- size ---------------------------------------------------------------------------------------


class Account(_Request):
    balance: Price
    currency: Annotated[str, Field(pattern=r"^[A-Z0-9]{2,16}$", examples=["USD"])]
    leverage: Annotated[float, Field(gt=0, le=10_000, allow_inf_nan=False)]


class RiskSettings(_Request):
    """``daily_loss_limit_pct`` and ``max_drawdown_pct`` are optional (Fadi, point 15): the
    backend applies both guards itself before calling ``/v1/size`` (B10)."""

    risk_per_trade_pct: Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)]
    daily_loss_limit_pct: Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)] | None = None
    max_drawdown_pct: Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)] | None = None


class SizeRequest(_Request):
    setup: Setup
    instrument_spec: InstrumentSpec
    account: Account
    risk: RiskSettings


class SizeResponse(_Response):
    """Money is USD only in v1 (Fadi, point 3): ``risk_usd`` is always USD, ai-service converts
    from the quote currency (e.g. JPY) itself."""

    lots: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    risk_usd: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    margin_required: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    feasible: bool
    warnings: list[str] = Field(default_factory=list)


# --- explain ------------------------------------------------------------------------------------


class ExplainRequest(_Request):
    setup: Setup
    lang: Literal["ar", "en"]


class ExplainResponse(_Response):
    """Shown to a user only when ``verified`` or ``template_used`` (the fixed template filled
    with the setup's own numbers); otherwise the explanation is unavailable (Fadi, extra 5)."""

    text: str = Field(min_length=1)
    verified: bool = Field(description="the text was checked against the setup's numbers")
    template_used: bool = Field(description="true when the fixed template was used")


# --- errors and health --------------------------------------------------------------------------


class ErrorItem(_Response):
    loc: list[str | int] = Field(default_factory=list)
    msg: str
    type: str | None = None


class ErrorResponse(_Response):
    """422 (FastAPI style)."""

    detail: list[ErrorItem] | str


class Health(_Response):
    status: Literal["ok"]
    versions: Versions | None = None
