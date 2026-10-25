"""``POST /v1/size`` (P6 task 6): lots for one setup and one account. Stateless: the backend holds
the open positions and the daily and drawdown limits (B10).

The lot arithmetic is ``app.scoring.lots``, vendored unchanged from
``libs/backtest/trading_backtest/sizing.py`` (B4), so ai-service and the platform size a trade the
same way:

* ``risk_amount = balance * risk_per_trade_pct / 100`` (account currency);
* the quote -> account rate comes from the setup's own price (``direct_rate``): 1 when the quote
  currency is the account currency (XAU/USD, EUR/USD, GBP/USD, AUD/USD for a USD account),
  ``1 / entry`` when the account currency is the base (USD/JPY, USD/CAD). Any other pair of
  currencies is not feasible in v1: no rate is assumed. This replaces ``Sizer.size`` of
  ``libs/backtest``, which treated the balance as quote currency (AUDIT §5: USD/JPY ~150x small);
* lots are rounded down to ``lot_step`` and limited by ``min_lot`` / ``max_lot``;
* ``margin_required = lots * contract_size * entry * rate * max(margin_rate, 1 / leverage)``.

Warnings, none of which changes the lots: the margin is above the balance (not feasible), and one
stop-out would lose more than the daily loss limit. Costs (spread, slippage) are not in the risk,
as in B4."""

from __future__ import annotations

from app.config import instruments
from app.contract import PRICED_STATES, SizeRequest, SizeResponse
from app.scoring.lots import ContractSpec, direct_rate, lots_for_risk


class UnknownSetup(ValueError):
    """The setup names no instrument ai-service knows (answered with 422)."""


def instrument_of(req: SizeRequest) -> str:
    """The setup's instrument: its ``instrument`` field (ai-service writes it), else the prefix of
    its id (``xauusd-intraday-...``)."""
    extra = req.setup.model_extra or {}
    symbol = str(extra.get("instrument") or req.setup.setup_id.split("-", 1)[0]).upper()
    if symbol not in instruments():
        raise UnknownSetup(f"setup {req.setup.setup_id!r}: unknown instrument {symbol!r}")
    return symbol


def size(req: SizeRequest) -> SizeResponse:
    setup, spec, account, risk = req.setup, req.instrument_spec, req.account, req.risk
    inst = instruments()[instrument_of(req)]
    if setup.state not in PRICED_STATES:
        return SizeResponse(
            lots=0.0,
            risk_usd=0.0,
            feasible=False,
            warnings=[f"a {setup.state.value} setup has no trade to size"],
        )
    quote = spec.quote_currency or inst.quote_currency
    base = inst.symbol[:3]
    rate = direct_rate(base, quote, account.currency, setup.entry)
    sized = lots_for_risk(
        account.balance * risk.risk_per_trade_pct / 100,
        setup.entry,
        setup.sl,
        ContractSpec(spec.contract_size, spec.lot_step, quote, spec.min_lot, spec.max_lot),
        account.currency,
        rate,
    )
    warnings = list(sized.warnings)
    feasible = sized.feasible
    margin = None
    if feasible:
        fraction = max(spec.margin_rate or 0.0, 1 / account.leverage)
        margin = round(sized.lots * spec.contract_size * setup.entry * rate * fraction, 2)
        if margin > account.balance:
            feasible = False
            warnings.append(
                f"the margin {margin:.2f} {account.currency} is above the balance"
                f" {account.balance:.2f} {account.currency}"
            )
    if risk.risk_per_trade_pct > risk.daily_loss_limit_pct:
        warnings.append(
            f"one stop-out ({risk.risk_per_trade_pct:g}%) would exceed the daily loss limit"
            f" ({risk.daily_loss_limit_pct:g}%)"
        )
    return SizeResponse(
        lots=sized.lots if feasible else 0.0,
        risk_usd=round(sized.risk_amount, 2) if feasible and sized.risk_amount else 0.0,
        margin_required=margin if feasible else None,
        feasible=feasible,
        warnings=warnings,
    )
