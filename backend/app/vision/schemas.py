"""The chart analysis result (Y14, docs/chart-analysis.md).

``ModelChartAnalysis`` is what Gemini must return (``response_schema``): plain types, so the
schema stays inside what structured output supports. ``finalize`` turns it into the stored
``ChartAnalysis``:

- confidences and the trend strength are clamped to 0..1;
- support and resistance keep only positive, finite numbers;
- the idea's prices must be on the right side (buy: stop < entry < target; sell: target <
  entry < stop). If they are not, the prices are dropped with a warning, and the rest of the
  result is kept;
- ``risk_reward`` is computed by code from the kept prices, never taken from the model;
- ``is_chart = false`` empties every other field;
- the disclaimer is added by code, in the requested language, never by the model.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["ar", "en"]

DISCLAIMERS: dict[str, str] = {
    "ar": "هذا التحليل آلي ولأغراض تعليمية فقط، وليس نصيحة مالية. قرار التداول ومخاطره عليك وحدك.",
    "en": "This is an automated analysis for educational purposes only, not financial advice. "
    "Trading decisions and their risks are yours alone.",
}

WARNINGS: dict[str, dict[str, str]] = {
    "ar": {
        "prices_dropped": "أُزيلت أسعار الفكرة لأنها غير متسقة مع اتجاه الصفقة "
        "(الشراء: الوقف < الدخول < الهدف؛ البيع: الهدف < الدخول < الوقف).",
    },
    "en": {
        "prices_dropped": "The idea's prices were removed because they are inconsistent with "
        "its direction (buy: stop < entry < target; sell: target < entry < stop).",
    },
}


# --- what the model returns ----------------------------------------------------------------------


class ModelPattern(BaseModel):
    name: str
    confidence: float
    description: str


class ModelIndicator(BaseModel):
    name: str
    reading: str


class ModelIdea(BaseModel):
    action: Literal["buy", "sell", "wait"]
    confidence: float
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None


class ModelChartAnalysis(BaseModel):
    is_chart: bool
    symbol_guess: str | None = None
    timeframe_guess: str | None = None
    trend: Literal["up", "down", "sideways"] | None = None
    trend_strength: float | None = None
    patterns: list[ModelPattern] = Field(default_factory=list)
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    indicators_seen: list[ModelIndicator] = Field(default_factory=list)
    idea: ModelIdea | None = None
    summary: str = ""
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- what is stored and returned -----------------------------------------------------------------


class Pattern(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    description: str


class Indicator(BaseModel):
    name: str
    reading: str


class Idea(BaseModel):
    action: Literal["buy", "sell", "wait"]
    confidence: float = Field(ge=0, le=1)
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = Field(
        default=None, description="computed from entry, stop and target (null without all three)"
    )


class ChartAnalysis(BaseModel):
    is_chart: bool
    symbol_guess: str | None = None
    timeframe_guess: str | None = None
    trend: Literal["up", "down", "sideways"] | None = None
    trend_strength: float | None = Field(default=None, ge=0, le=1)
    patterns: list[Pattern] = Field(default_factory=list)
    support_levels: list[float] = Field(
        default_factory=list, description="only when the price axis is readable"
    )
    resistance_levels: list[float] = Field(default_factory=list)
    indicators_seen: list[Indicator] = Field(default_factory=list)
    idea: Idea | None = None
    summary: str = Field(default="", description="2-4 sentences in the requested language")
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = Field(description="fixed per language, added by the backend")


def clamp01(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return 0.0
    return min(1.0, max(0.0, float(value)))


def _price(value: float | None) -> float | None:
    return float(value) if value is not None and math.isfinite(value) and value > 0 else None


def _levels(values: list[float]) -> list[float]:
    return [float(v) for v in values if v is not None and math.isfinite(v) and v > 0]


def _idea(idea: ModelIdea, language: str) -> tuple[Idea, list[str]]:
    entry, stop, target = _price(idea.entry), _price(idea.stop_loss), _price(idea.take_profit)
    # the known prices in the order they must rise: buy stop < entry < target, sell the reverse
    sequence = (target, entry, stop) if idea.action == "sell" else (stop, entry, target)
    ordered = [p for p in sequence if p is not None]
    consistent = idea.action == "wait" or all(
        a < b for a, b in zip(ordered, ordered[1:], strict=False)
    )
    warnings = []
    if not consistent:
        entry = stop = target = None
        warnings.append(WARNINGS[language]["prices_dropped"])
    rr = None
    if None not in (entry, stop, target) and idea.action != "wait" and entry != stop:
        rr = round(abs(target - entry) / abs(entry - stop), 2)
    return (
        Idea(
            action=idea.action,
            confidence=clamp01(idea.confidence) or 0.0,
            entry=entry,
            stop_loss=stop,
            take_profit=target,
            risk_reward=rr,
        ),
        warnings,
    )


def finalize(raw: ModelChartAnalysis, language: str) -> ChartAnalysis:
    """The model's answer, checked and completed by code (module docstring)."""
    disclaimer = DISCLAIMERS[language]
    if not raw.is_chart:
        return ChartAnalysis(is_chart=False, disclaimer=disclaimer)
    idea, extra = (None, []) if raw.idea is None else _idea(raw.idea, language)
    return ChartAnalysis(
        is_chart=True,
        symbol_guess=(raw.symbol_guess or None),
        timeframe_guess=(raw.timeframe_guess or None),
        trend=raw.trend,
        trend_strength=clamp01(raw.trend_strength),
        patterns=[
            Pattern(name=p.name, confidence=clamp01(p.confidence) or 0.0, description=p.description)
            for p in raw.patterns
        ],
        support_levels=_levels(raw.support_levels),
        resistance_levels=_levels(raw.resistance_levels),
        indicators_seen=[Indicator(name=i.name, reading=i.reading) for i in raw.indicators_seen],
        idea=idea,
        summary=raw.summary.strip(),
        reasoning=[r for r in raw.reasoning if r.strip()],
        warnings=[*[w for w in raw.warnings if w.strip()], *extra],
        disclaimer=disclaimer,
    )
