"""Workspaces: the saved trading screen (``state``, schema_version 1) and the API bodies.

The field-level rules live in these Pydantic models (``extra="forbid"`` everywhere, so typos are
rejected). Rules that span fields or need the indicator/strategy registries are in
:func:`state_errors`; the instrument lookups are in app/services/workspace_service.py. Both
report FastAPI-style errors (``loc`` = the JSON path), so clients get one format.
"""

import json
import math
import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Annotated, Any, Literal

import trading_indicators as ti
import trading_strategies as ts
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.candle import Timeframe
from app.models.custom_strategy import KEY_PREFIX as CUSTOM_PREFIX

SCHEMA_VERSION = 1
MAX_STATE_BYTES = 256 * 1024
MAX_INDICATORS_PER_PANEL = 10
MAX_STRATEGIES_PER_PANEL = 5
MAX_DRAWINGS_PER_PANEL = 200
MAX_WATCHLIST = 50
MAX_TEXT = 200

LayoutType = Literal["1x1", "1x2", "2x1", "2x2", "1+2"]
# panels per layout, and how many sizes its main split has
LAYOUT_PANELS: dict[str, int] = {"1x1": 1, "1x2": 2, "2x1": 2, "2x2": 4, "1+2": 3}
LAYOUT_SIZES: dict[str, int] = {"1x1": 1, "1x2": 2, "2x1": 2, "2x2": 2, "1+2": 2}
SIZES_TOLERANCE = 0.01

DrawingType = Literal["trendline", "horizontal", "vertical", "rectangle", "fibonacci", "text"]
DRAWING_POINTS: dict[str, int] = {
    "trendline": 2,
    "horizontal": 1,
    "vertical": 1,
    "rectangle": 2,
    "fibonacci": 2,
    "text": 1,
}

ItemId = Annotated[str, StringConstraints(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
WorkspaceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Layout(_Strict):
    type: LayoutType = "1x1"
    # relative sizes of the layout's main split (1x1: 1 value, every other layout: 2), sum 1;
    # omitted = equal parts
    sizes: list[Annotated[float, Field(gt=0, le=1)]] | None = None


class Sync(_Strict):
    crosshair: bool = True
    timeframe: bool = False
    instrument: bool = False


class IndicatorOverlay(_Strict):
    id: ItemId
    name: str = Field(min_length=1, max_length=32)
    params: dict[str, Any] = Field(default_factory=dict)  # resolved with defaults on save
    visible: bool = True
    color: Color | None = None


class StrategyOverlay(_Strict):
    id: ItemId
    # a global key, or custom:<uuid> (one of your custom strategies or a public one)
    strategy_key: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)  # resolved with defaults on save
    visible: bool = True
    # read-only on a workspace read: the strategy cannot be used (custom strategy deleted or
    # made private by its author); accepted on write and ignored
    unavailable: bool | None = Field(default=None, exclude=True)


class Point(_Strict):
    time: int = Field(ge=0, description="unix seconds")
    price: float

    @field_validator("price")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("price must be a finite number")
        return value


class DrawingStyle(_Strict):
    color: Color = "#2196F3"
    width: int = Field(default=1, ge=1, le=10)


class Drawing(_Strict):
    id: ItemId
    type: DrawingType
    points: list[Point] = Field(min_length=1, max_length=2)
    style: DrawingStyle = Field(default_factory=DrawingStyle)
    text: str | None = Field(default=None, max_length=MAX_TEXT)


class InstrumentInfo(BaseModel):
    """Read-only, added to each panel on read."""

    id: uuid.UUID
    symbol: str
    source: str
    is_active: bool


class Panel(_Strict):
    id: ItemId
    instrument_id: uuid.UUID | None = None  # null = no instrument chosen yet (empty chart)
    timeframe: Timeframe = Timeframe.h1
    chart_type: Literal["candles", "heikin_ashi", "line", "area", "bars"] = "candles"
    indicators: list[IndicatorOverlay] = Field(
        default_factory=list, max_length=MAX_INDICATORS_PER_PANEL
    )
    strategies: list[StrategyOverlay] = Field(
        default_factory=list, max_length=MAX_STRATEGIES_PER_PANEL
    )
    drawings: list[Drawing] = Field(default_factory=list, max_length=MAX_DRAWINGS_PER_PANEL)
    # read-only fields of a workspace read: accepted on write (so a read can be sent back as
    # is) but ignored and never stored
    instrument: InstrumentInfo | None = Field(default=None, exclude=True)
    unavailable: bool | None = Field(default=None, exclude=True)


class WorkspaceState(_Strict):
    """The whole screen, saved in one call (schema_version 1)."""

    layout: Layout = Field(default_factory=Layout)
    sync: Sync = Field(default_factory=Sync)
    panels: list[Panel] = Field(min_length=1, max_length=4)
    watchlist: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_WATCHLIST)
    active_panel: ItemId

    def stored(self) -> dict[str, Any]:
        """The JSON document stored in the database."""
        return self.model_dump(mode="json")


Loc = tuple[str | int, ...]


def error(loc: Loc, msg: str, kind: str = "value_error") -> dict[str, Any]:
    return {"loc": list(loc), "msg": msg, "type": kind}


def state_errors(
    state: WorkspaceState,
    prefix: Loc = ("body", "state"),
    custom_ok: Collection[str] = (),
) -> list[dict[str, Any]]:
    """Cross-field rules and registry validation. Resolves indicator and strategy params in
    place (defaults filled in), so the stored state is explicit."""
    errors: list[dict[str, Any]] = []

    layout = state.layout
    expected = LAYOUT_PANELS[layout.type]
    if len(state.panels) != expected:
        errors.append(
            error(
                (*prefix, "panels"),
                f"layout {layout.type} needs {expected} panel(s), got {len(state.panels)}",
            )
        )
    if layout.sizes is not None:
        n = LAYOUT_SIZES[layout.type]
        if len(layout.sizes) != n:
            errors.append(
                error(
                    (*prefix, "layout", "sizes"),
                    f"layout {layout.type} needs {n} size(s), got {len(layout.sizes)}",
                )
            )
        elif abs(sum(layout.sizes) - 1) > SIZES_TOLERANCE:
            errors.append(
                error(
                    (*prefix, "layout", "sizes"), f"sizes must sum to 1, got {sum(layout.sizes):g}"
                )
            )

    seen: dict[str, Loc] = {}

    def unique(item_id: str, loc: Loc) -> None:
        if item_id in seen:
            errors.append(
                error(loc, f"duplicate id '{item_id}' (also used at {_path(seen[item_id])})")
            )
        else:
            seen[item_id] = loc

    for p, panel in enumerate(state.panels):
        ploc = (*prefix, "panels", p)
        unique(panel.id, (*ploc, "id"))
        for i, ind in enumerate(panel.indicators):
            iloc = (*ploc, "indicators", i)
            unique(ind.id, (*iloc, "id"))
            try:
                spec = ti.get_indicator(ind.name)
            except ValueError as exc:
                errors.append(error((*iloc, "name"), str(exc)))
                continue
            try:
                ind.params = spec.resolve(ind.params)
            except ValueError as exc:
                errors.append(error((*iloc, "params"), str(exc)))
        for s, strat in enumerate(panel.strategies):
            sloc = (*ploc, "strategies", s)
            unique(strat.id, (*sloc, "id"))
            if strat.strategy_key.startswith(CUSTOM_PREFIX):
                # custom strategies: checked by the service (access needs the database)
                if strat.strategy_key.lower() not in custom_ok:
                    errors.append(
                        error(
                            (*sloc, "strategy_key"),
                            f"unknown or inaccessible custom strategy {strat.strategy_key}",
                        )
                    )
                elif strat.params:
                    errors.append(error((*sloc, "params"), "custom strategies take no params"))
                else:
                    strat.strategy_key = strat.strategy_key.lower()
                continue
            try:
                strategy = ts.get_strategy(strat.strategy_key)
            except ValueError as exc:
                errors.append(error((*sloc, "strategy_key"), str(exc)))
                continue
            try:
                strat.params = strategy.resolve(strat.params)
            except ValueError as exc:
                errors.append(error((*sloc, "params"), str(exc)))
        for d, drawing in enumerate(panel.drawings):
            dloc = (*ploc, "drawings", d)
            unique(drawing.id, (*dloc, "id"))
            needed = DRAWING_POINTS[drawing.type]
            if len(drawing.points) != needed:
                errors.append(
                    error(
                        (*dloc, "points"),
                        f"a {drawing.type} drawing needs {needed} point(s), "
                        f"got {len(drawing.points)}",
                    )
                )
            if drawing.type == "text" and not drawing.text:
                errors.append(error((*dloc, "text"), "a text drawing needs a non-empty text"))

    if state.active_panel not in {panel.id for panel in state.panels}:
        errors.append(error((*prefix, "active_panel"), f"no panel with id '{state.active_panel}'"))
    listed: set[uuid.UUID] = set()
    for w, instrument_id in enumerate(state.watchlist):
        if instrument_id in listed:
            errors.append(error((*prefix, "watchlist", w), f"duplicate instrument {instrument_id}"))
        listed.add(instrument_id)
    return errors


def _path(loc: Loc) -> str:
    out = ""
    for part in loc[1:]:  # without "body"
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


# --- API bodies / responses ------------------------------------------------------------------


Template = Literal["default", "blank", "multi_chart"]


class WorkspaceCreate(_Strict):
    name: WorkspaceName
    state: WorkspaceState | None = None
    template: Template | None = None  # neither state nor template: "blank"


class WorkspaceStateUpdate(_Strict):
    state: WorkspaceState
    version: int | None = Field(default=None, ge=1, description="or the If-Match header")


class WorkspaceUpdate(_Strict):
    name: WorkspaceName | None = None
    is_default: Literal[True] | None = Field(
        default=None, description="true makes this the default; unset by choosing another one"
    )
    version: int | None = Field(default=None, ge=1, description="optional check (or If-Match)")


class WorkspaceOrder(_Strict):
    ids: list[uuid.UUID] = Field(min_length=1)


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    position: int
    is_default: bool
    version: int
    panel_count: int
    is_shared: bool
    updated_at: datetime


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    position: int
    is_default: bool
    version: int
    schema_version: int
    is_shared: bool
    share_slug: str | None
    # panels carry read-only ``instrument`` and ``unavailable``
    state: dict[str, Any]
    unavailable_instrument_ids: list[uuid.UUID]  # panels and watchlist
    created_at: datetime
    updated_at: datetime


class ShareRead(BaseModel):
    is_shared: bool
    share_slug: str | None


class SharedOwner(BaseModel):
    display_name: str
    role: str


class SharedWorkspaceRead(BaseModel):
    """A shared workspace as other users see it: no workspace or user ids."""

    name: str
    owner: SharedOwner
    schema_version: int
    state: dict[str, Any]
    unavailable_instrument_ids: list[uuid.UUID]
    updated_at: datetime


class SharedImport(_Strict):
    name: WorkspaceName | None = None  # default: the shared workspace's name (made unique)


def state_json_schema() -> dict[str, Any]:
    """The JSON Schema of ``state`` (docs/workspace-state.schema.json)."""
    schema = WorkspaceState.model_json_schema()
    schema["$id"] = "workspace-state.schema.json"
    schema["description"] = (
        f"Workspace state, schema_version {SCHEMA_VERSION}. Panel.instrument and "
        "Panel.unavailable are read-only (ignored on write). Cross-field rules (panels per "
        "layout, unique ids, active_panel, drawing points, registry params, instrument "
        f"existence, {MAX_STATE_BYTES} bytes max) are checked by the API: docs/workspaces.md."
    )
    return schema


if __name__ == "__main__":  # python -m app.schemas.workspaces > ../docs/workspace-state.schema.json
    print(json.dumps(state_json_schema(), indent=2))
