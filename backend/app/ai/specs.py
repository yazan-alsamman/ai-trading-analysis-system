"""The ``instrument_spec`` of ai-service requests (B7 contract): the B4 contract specs of an
instrument. Used by sizing (B10) and by evaluate requests (B9)."""

import hashlib
import json

from app.ai.contract import InstrumentSpec
from app.models.instrument import Instrument

REQUIRED = ("contract_size", "tick_size", "lot_step", "min_lot", "max_lot", "price_basis")


class MissingSpecs(ValueError):
    """The instrument lacks contract specs ai-service needs (docs/instruments.md)."""


def instrument_spec(instrument: Instrument) -> InstrumentSpec:
    missing = [name for name in REQUIRED if getattr(instrument, name) is None]
    if missing:
        raise MissingSpecs(
            f"{instrument.source}:{instrument.symbol} has no {', '.join(missing)} "
            "(set them with PATCH /admin/instruments/{id})"
        )
    return InstrumentSpec(
        contract_size=instrument.contract_size,
        tick_size=instrument.tick_size,
        lot_step=instrument.lot_step,
        min_lot=instrument.min_lot,
        max_lot=instrument.max_lot,
        price_basis=instrument.price_basis,
        session_calendar=instrument.session_calendar,
        quote_currency=instrument.pnl_currency,
        margin_rate=instrument.margin_rate,
    )


def spec_hash(spec: InstrumentSpec) -> str:
    return hashlib.sha256(
        json.dumps(spec.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
