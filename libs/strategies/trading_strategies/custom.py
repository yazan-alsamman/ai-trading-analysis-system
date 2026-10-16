"""Custom strategies as a whole: validating and building one from its ``kind`` (``builder`` or
``composite``) and definition, reproducible snapshots and their hash, and the machine-readable
schema the web and mobile editors are generated from.

A **snapshot** is everything needed to rebuild a custom strategy without a database::

    {"kind": "composite", "definition": {...}, "members": {"custom:<uuid>": {"kind", "definition"}}}

``members`` holds every custom strategy reached through composites (flattened, normalised).
:func:`snapshot_hash` of it identifies the setup: it changes whenever the definition, or the
definition of a custom member, changes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import trading_indicators as ti

from trading_strategies.base import Strategy
from trading_strategies.builder import (
    CATEGORIES,
    COMPARE_OPS,
    MAX_BARS,
    MAX_CONDITIONS,
    MAX_DEPTH,
    MAX_MULTIPLIER,
    MAX_SHIFT,
    PRICE_FIELDS,
    SCHEMA_VERSION,
    STRENGTHS,
    BuilderDefinition,
    BuilderStrategy,
    DefinitionError,
    builder_errors,
    issue,
)
from trading_strategies.composite import (
    MAX_MEMBERS,
    MAX_NESTING,
    MAX_WINDOW,
    MIN_MEMBERS,
    MODES,
    CompositeDefinition,
    CompositeStrategy,
    Resolver,
    composite_errors,
)
from trading_strategies.registry import STRATEGIES

KINDS = ("builder", "composite")


@dataclass
class Validation:
    """Result of :func:`validate`: the normalised definition and its snapshot, or errors."""

    errors: list[dict[str, Any]] = field(default_factory=list)
    definition: dict[str, Any] | None = None
    snapshot: dict[str, Any] | None = None
    history: int | None = None

    @property
    def valid(self) -> bool:
        return not self.errors


def validate(
    kind: str, definition: Any, resolver: Resolver | None = None, *, key: str | None = None
) -> Validation:
    """Validate a definition; never raises for bad input. ``key`` is the strategy's own
    ``custom:<uuid>`` when it has one (cycle detection)."""
    if kind == "builder":
        normalised, errors = builder_errors(definition)
        resolved: dict[str, dict[str, Any]] = {}
    elif kind == "composite":
        normalised, errors, resolved = composite_errors(definition, resolver, ref=key)
    else:
        return Validation(errors=[issue(("kind",), f"must be one of {', '.join(KINDS)}")])
    if errors:
        return Validation(errors=errors)
    snap = {"kind": kind, "definition": normalised, "members": resolved}
    return Validation(definition=normalised, snapshot=snap, history=from_snapshot(snap).history())


def build(
    kind: str,
    definition: Mapping[str, Any],
    resolver: Resolver | None = None,
    *,
    key: str | None = None,
    title: str | None = None,
) -> Strategy:
    """The :class:`Strategy` of a definition (:class:`DefinitionError` if it is invalid)."""
    checked = validate(kind, definition, resolver, key=key)
    if not checked.valid:
        raise DefinitionError(checked.errors)
    assert checked.snapshot is not None
    return from_snapshot(checked.snapshot, key=key, title=title)


def snapshot(
    kind: str, definition: Mapping[str, Any], resolver: Resolver | None = None, **kw: Any
) -> dict[str, Any]:
    checked = validate(kind, definition, resolver, **kw)
    if not checked.valid:
        raise DefinitionError(checked.errors)
    assert checked.snapshot is not None
    return checked.snapshot


def from_snapshot(
    snap: Mapping[str, Any], *, key: str | None = None, title: str | None = None
) -> Strategy:
    """Rebuild a strategy from a snapshot alone (no resolver, no database)."""
    members = snap.get("members") or {}

    def resolver(ref: str) -> tuple[str, Mapping[str, Any]]:
        entry = members[ref]  # KeyError is a LookupError: reported as inaccessible
        return entry["kind"], entry["definition"]

    names = {"title": title or key or "Custom strategy"}
    if snap["kind"] == "builder":
        return BuilderStrategy(snap["definition"], key=key or "builder", **names)
    if snap["kind"] == "composite":
        return CompositeStrategy(snap["definition"], resolver, key=key or "composite", **names)
    raise DefinitionError([issue(("kind",), f"must be one of {', '.join(KINDS)}")])


def snapshot_hash(snap: Mapping[str, Any]) -> str:
    """Stable identity of a custom setup (32 hex characters, like ``params_hash``)."""
    payload = json.dumps(
        {"kind": snap["kind"], "definition": snap["definition"], "members": snap["members"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


# --- schema for editors ----------------------------------------------------------------------

OP_TITLES = {
    ">": "is greater than",
    "<": "is less than",
    ">=": "is greater than or equal to",
    "<=": "is less than or equal to",
    "crosses_above": "crosses above",
    "crosses_below": "crosses below",
    "between": "is between (inclusive)",
    "rising": "is rising (strictly, over N bars)",
    "falling": "is falling (strictly, over N bars)",
}


def operand_catalog() -> dict[str, Any]:
    """What an editor needs besides the JSON Schemas: indicators with their params and
    outputs, price fields, ops with their operands, modes and limits."""
    ops = [{"op": op, "title": OP_TITLES[op], "operands": ["left", "right"]} for op in COMPARE_OPS]
    ops.append(
        {"op": "between", "title": OP_TITLES["between"], "operands": ["value", "lower", "upper"]}
    )
    for op in ("rising", "falling"):
        ops.append(
            {
                "op": op,
                "title": OP_TITLES[op],
                "operands": ["value"],
                "bars": {"min": 1, "max": MAX_BARS},
            }
        )
    indicators = [
        {
            "name": i.name,
            "title": i.title,
            "category": i.category,
            "params": [p.to_dict() for p in i.params],
            "outputs": list(i.outputs),
            "output_required": len(i.outputs) > 1,
            "levels": list(i.levels),
        }
        for i in ti.INDICATORS.values()
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kinds": list(KINDS),
        "builder": {
            "operand_types": ["indicator", "price", "constant"],
            "indicators": indicators,
            "price_fields": list(PRICE_FIELDS),
            "ops": ops,
            "groups": ["all", "any"],
            "strengths": list(STRENGTHS),
            "categories": list(CATEGORIES),
        },
        "composite": {
            "modes": list(MODES),
            "strategies": [
                {"key": s.key, "title": s.title, "params": [p.to_dict() for p in s.params]}
                for s in STRATEGIES.values()
            ],
            "custom_ref": "custom:<uuid>",
        },
        "limits": {
            "max_depth": MAX_DEPTH,
            "max_conditions": MAX_CONDITIONS,
            "shift": {"min": 0, "max": MAX_SHIFT},
            "multiplier": {"min_exclusive": 0, "max": MAX_MULTIPLIER, "default": 1},
            "bars": {"min": 1, "max": MAX_BARS},
            "members": {"min": MIN_MEMBERS, "max": MAX_MEMBERS},
            "window": {"min": 1, "max": MAX_WINDOW},
            "threshold": {"min_exclusive": 0, "max": 1},
            "max_nesting": MAX_NESTING,
        },
    }


def json_schemas() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) of both definitions."""
    return {
        "builder": BuilderDefinition.model_json_schema(),
        "composite": CompositeDefinition.model_json_schema(),
    }
