from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AI Trading Inference Service", version="0.1.0")


class SignalRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"


class SignalResponse(BaseModel):
    symbol: str
    timeframe: str
    direction: Literal["buy", "sell", "hold"]
    confidence: float
    model_version: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/signal", response_model=SignalResponse)
def signal(req: SignalRequest) -> SignalResponse:
    # Placeholder until the first trained model (F06) is wired in.
    return SignalResponse(
        symbol=req.symbol,
        timeframe=req.timeframe,
        direction="hold",
        confidence=0.0,
        model_version="placeholder",
    )
