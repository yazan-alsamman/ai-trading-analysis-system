"""Position size in lots for instruments with contract specs (CFD / FX style).

The value of a price move depends on the contract and on the account currency::

    value_per_price_unit = contract_size * conversion_rate
    risk_per_lot         = |entry - stop| * value_per_price_unit
    lots                 = risk_amount / risk_per_lot   (rounded DOWN to lot_step, then clamped)

``conversion_rate`` is how much one unit of the instrument's quote (P&L) currency is worth in
the account currency: 1 when they are the same, ``1 / entry`` for a USD/xxx pair with a USD
account (one JPY = 1/150 USD at USD/JPY 150), otherwise the price of a matching ``XXX/ACCOUNT``
(or ``1 /`` the price of ``ACCOUNT/XXX``) instrument, which the caller looks up. Without a rate
the size is not feasible: a rate of 1 is never assumed.

Examples (docs/instruments.md): XAU/USD, 100 oz per lot, USD account, entry 2400, stop 2395,
risk 20 USD -> 500 USD per lot -> 0.04 lots. USD/JPY at 150.000, stop 149.500, risk 100 USD ->
0.5 * 100,000 / 150 = 333.33 USD per lot -> 0.30 lots.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Floating-point slack when flooring to the lot step: 0.3 / 0.01 is 29.999999999999996.
STEP_EPSILON = 1e-9


@dataclass(frozen=True)
class ContractSpec:
    """The specs sizing needs. ``quote_currency`` is the currency of the P&L per price unit."""

    contract_size: float
    lot_step: float
    quote_currency: str
    min_lot: float | None = None
    max_lot: float | None = None

    def __post_init__(self) -> None:
        if not self.contract_size > 0 or not self.lot_step > 0:
            raise ValueError("contract_size and lot_step must be > 0")
        if self.min_lot is not None and self.max_lot is not None and self.min_lot > self.max_lot:
            raise ValueError("min_lot must be <= max_lot")


@dataclass
class LotSize:
    """``lots`` is what to trade (0 when not ``feasible``); ``warnings`` say why or what was
    adjusted. Money amounts are in the account currency."""

    lots: float
    feasible: bool
    warnings: list[str] = field(default_factory=list)
    raw_lots: float | None = None  # before rounding and limits
    risk_per_lot: float | None = None
    risk_amount: float | None = None  # at ``lots``
    value_per_price_unit: float | None = None  # per lot
    conversion_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        def num(x: float | None, digits: int = 8) -> float | None:
            return None if x is None or not math.isfinite(x) else round(float(x), digits)

        return {
            "lots": num(self.lots),
            "feasible": self.feasible,
            "warnings": list(self.warnings),
            "raw_lots": num(self.raw_lots, 10),
            "risk_per_lot": num(self.risk_per_lot, 4),
            "risk_amount": num(self.risk_amount, 4),
            "value_per_price_unit": num(self.value_per_price_unit, 8),
            "conversion_rate": num(self.conversion_rate, 10),
        }


def direct_rate(base: str, quote: str, account: str, entry: float) -> float | None:
    """The conversion rate that needs no other market: 1 when the quote currency is the
    account currency, ``1 / entry`` when the account currency is the base (USD/JPY for a USD
    account). None otherwise (look up a matching market)."""
    if quote == account:
        return 1.0
    if base == account and entry > 0:
        return 1.0 / entry
    return None


def value_per_price_unit(
    contract_size: float,
    quote_currency: str,
    account_currency: str,
    conversion_rate: float | None,
) -> float:
    """Account-currency value of a 1.0 price move on 1.0 lot. Raises ``ValueError`` without a
    usable rate (it never assumes 1 for different currencies)."""
    if not contract_size > 0:
        raise ValueError("contract_size must be > 0")
    if quote_currency == account_currency:
        if conversion_rate is not None and conversion_rate != 1.0:
            raise ValueError("the conversion rate between the same currency must be 1")
        return float(contract_size)
    if conversion_rate is None or not math.isfinite(conversion_rate) or conversion_rate <= 0:
        raise ValueError(f"no conversion rate from {quote_currency} to {account_currency}")
    return float(contract_size) * float(conversion_rate)


def _decimals(step: float) -> int:
    text = f"{step:.12f}".rstrip("0")
    return len(text.split(".")[1]) if "." in text else 0


def round_lots(raw_lots: float, spec: ContractSpec) -> tuple[float, bool, list[str]]:
    """(lots, feasible, warnings): ``raw_lots`` rounded down to ``lot_step``, capped at
    ``max_lot``; below ``min_lot`` (or one step) it is 0 and not feasible."""
    warnings: list[str] = []
    if not math.isfinite(raw_lots) or raw_lots <= 0:
        return 0.0, False, ["nothing to trade"]
    steps = math.floor(raw_lots / spec.lot_step + STEP_EPSILON)
    lots = round(steps * spec.lot_step, _decimals(spec.lot_step))
    if spec.max_lot is not None and lots > spec.max_lot:
        warnings.append(f"capped at the maximum of {spec.max_lot:g} lots")
        lots = spec.max_lot
    minimum = spec.min_lot if spec.min_lot is not None else spec.lot_step
    if lots < minimum - STEP_EPSILON:
        warnings.append(f"below the minimum of {minimum:g} lots")
        return 0.0, False, warnings
    return lots, True, warnings


def lots_for_risk(
    risk_amount: float,
    entry: float,
    stop: float,
    spec: ContractSpec,
    account_currency: str,
    conversion_rate: float | None,
) -> LotSize:
    """Lots that lose at most ``risk_amount`` (account currency) if the stop is hit, rounded
    down to ``lot_step`` and clamped to ``min_lot``/``max_lot``. Price-move risk only: costs
    (spread, commission) are not included."""
    if not risk_amount > 0:
        return LotSize(0.0, False, ["the risk amount must be > 0"])
    move = abs(entry - stop)
    if not move > 0:
        return LotSize(0.0, False, ["the stop must differ from the entry"])
    try:
        per_unit = value_per_price_unit(
            spec.contract_size, spec.quote_currency, account_currency, conversion_rate
        )
    except ValueError as exc:
        return LotSize(0.0, False, [str(exc)], conversion_rate=conversion_rate)
    rate = 1.0 if spec.quote_currency == account_currency else conversion_rate
    risk_per_lot = move * per_unit
    raw = risk_amount / risk_per_lot
    lots, feasible, warnings = round_lots(raw, spec)
    if not feasible and spec.min_lot is not None and raw > 0:
        warnings.append(
            f"the minimum {spec.min_lot:g} lots would risk {spec.min_lot * risk_per_lot:.2f} "
            f"{account_currency}, more than the {risk_amount:.2f} {account_currency} allowed"
        )
    return LotSize(
        lots=lots,
        feasible=feasible,
        warnings=warnings,
        raw_lots=raw,
        risk_per_lot=risk_per_lot,
        risk_amount=lots * risk_per_lot,
        value_per_price_unit=per_unit,
        conversion_rate=rate,
    )
