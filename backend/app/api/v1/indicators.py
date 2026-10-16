import json
import uuid

import trading_indicators as ti
from fastapi import APIRouter, Response

from app.api.deps import IndicatorsReader, SessionDep
from app.api.limits import EXPENSIVE
from app.schemas.indicators import IndicatorsRequest, IndicatorsResponse
from app.services import indicator_service, market_service

router = APIRouter(tags=["indicators"])


@router.get("/indicators")
async def indicator_catalog(_: IndicatorsReader) -> list[dict]:
    """Every available indicator: params (type, default, min, max), outputs, placement, levels
    and the warm-up (``lookback``) with the default params."""
    return ti.catalog()


@router.post(
    "/market/instruments/{instrument_id}/indicators",
    response_model=IndicatorsResponse,
    openapi_extra=EXPENSIVE,
)
async def compute_indicators(
    instrument_id: uuid.UUID, data: IndicatorsRequest, _: IndicatorsReader, session: SessionDep
):
    """Indicator lines over the same window ``GET .../candles`` returns for these parameters
    (without ``start``: the latest ``limit`` candles). Warm-up history is loaded automatically,
    so values are null only when not enough history exists."""
    indicators = indicator_service.resolve(data.indicators)
    await market_service.get_instrument_or_404(session, instrument_id)
    results = await indicator_service.compute_indicators(
        session,
        instrument_id,
        data.timeframe,
        indicators,
        start=data.start,
        end=data.end,
        limit=data.limit,
    )
    payload = {
        "instrument_id": str(instrument_id),
        "timeframe": data.timeframe.value,
        "results": results,
    }
    # Up to 10 x 5,000 points per output: the service already builds exactly the documented
    # shape, so serialize once instead of validating every point again (~2x faster).
    # allow_nan=False turns any NaN that slipped through into an error, not invalid JSON.
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    return Response(content=body, media_type="application/json")
