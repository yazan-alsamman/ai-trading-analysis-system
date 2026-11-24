import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.vision.schemas import ChartAnalysis


class ChartImageInfo(BaseModel):
    sha256: str
    bytes: int
    width: int
    height: int
    mime: str = Field(description="the uploaded type (from the magic bytes)")


class ChartUsage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None


class ChartAnalysisRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: Literal["ok", "not_chart", "refused", "error"]
    language: Literal["ar", "en"]
    symbol_hint: str | None
    timeframe_hint: str | None
    model: str
    prompt_version: str
    image: ChartImageInfo = Field(description="the image itself is never stored")
    result: ChartAnalysis | None = Field(description="the analysis (status ok or not_chart)")
    error: dict[str, Any] | None = Field(description="{code, message} (status refused or error)")
    usage: ChartUsage
    cached: bool = Field(
        default=False, description="the same image, language and hints within 24 h: no new call"
    )


class ChartAnalysisPage(BaseModel):
    items: list[ChartAnalysisRead]
    total: int
    limit: int
    offset: int


class ChartQuota(BaseModel):
    limit: int = Field(description="analyses per UTC day for your role")
    used: int
    remaining: int
    resets_at: datetime = Field(description="the next 00:00 UTC")
