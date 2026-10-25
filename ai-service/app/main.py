"""ai-service: the stateless inference service (contract B7, ``app/contract.py``).

    POST /v1/evaluate   the bar that just closed -> new setups, transitions, abstentions (P6)
    POST /v1/size       lots for one setup and one account (P6)
    GET  /health        status and versions

``/v1/explain`` follows in P7."""

from fastapi import FastAPI, HTTPException

from app.contract import EvaluateRequest, SizeRequest, SizeResponse
from app.live.evaluate import (
    FEATURES_VERSION,
    SERVICE_VERSION,
    LiveEvaluateResponse,
    UnknownInput,
    evaluate,
    versions,
)
from app.scoring.size import UnknownSetup, size

app = FastAPI(title="AI Trading Inference Service", version=SERVICE_VERSION)


@app.get("/health")
def health() -> dict:
    """The contract's ``Health`` plus the service version."""
    v = versions("intraday", "XAUUSD")
    return {
        "status": "ok",
        "versions": {
            "strategy": v["strategy"],
            "model": None,
            "features": FEATURES_VERSION,
            "service": SERVICE_VERSION,
        },
    }


@app.post("/v1/evaluate", response_model=LiveEvaluateResponse)
def evaluate_bar(req: EvaluateRequest) -> LiveEvaluateResponse:
    try:
        return evaluate(req)
    except UnknownInput as e:
        detail = [{"loc": ["body", e.field], "msg": str(e), "type": "value_error"}]
        raise HTTPException(status_code=422, detail=detail) from e


@app.post("/v1/size", response_model=SizeResponse)
def size_setup(req: SizeRequest) -> SizeResponse:
    try:
        return size(req)
    except UnknownSetup as e:
        detail = [{"loc": ["body", "setup", "setup_id"], "msg": str(e), "type": "value_error"}]
        raise HTTPException(status_code=422, detail=detail) from e
