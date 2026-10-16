"""Builder strategies: rules (indicator conditions combined with AND/OR) as a JSON document.

The definition is data, never code: it is validated with Pydantic (unknown keys are rejected),
indicator names and parameters go through the ``trading_indicators`` registry, and the rules
are evaluated with vectorised numpy. Nothing a user writes is ever evaluated or parsed as an
expression.

Definition (``schema_version`` 1)::

    {
      "schema_version": 1,
      "buy":  {"all": [<condition or group>, ...]},
      "sell": {"any": [...]},
      "strength": "fixed" | "rule_ratio",
      "category": "trend" | "mean_reversion" | "breakout" | "momentum"
    }

Operands: ``{"type": "indicator", "name", "params", "output"}``, ``{"type": "price", "field"}``
or ``{"type": "constant", "value"}``, each with an optional ``"shift": n`` (value ``n`` bars
ago, 0-100); indicator and price operands also take an optional ``"multiplier"`` (a number,
default 1), e.g. ``1.5`` x the volume SMA.

Conditions: ``{"left", "op", "right"}`` with ``>``, ``<``, ``>=``, ``<=``, ``crosses_above``,
``crosses_below``; ``{"op": "between", "value", "lower", "upper"}`` (inclusive);
``{"op": "rising" | "falling", "value", "bars"}`` (strictly, over ``bars`` bars, 1-50).

Semantics:

* **Edge-triggered.** A side fires on the bar where its rule tree becomes true after being false
  on the previous bar; a tree that stays true does not fire again until it was false once.
* **Conflict.** If buy and sell fire on the same bar, neither is emitted (no signal at all).
* **NaN.** A condition that reads a NaN (warm-up, gaps, shifted out of the data) is false.
* ``strength``: ``fixed`` = 1.0; ``rule_ratio`` = the fraction of the top-level group's
  children that are true on the signal bar.
* ``reason`` = ``builder_buy`` / ``builder_sell``; ``details`` = the operand values of every
  top-level child on the signal bar.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal, Union

import numpy as np
import pandas as pd
import trading_indicators as ti
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    ValidationError,
    field_validator,
)

from trading_strategies.base import BUY, Strategy, crossed_above, crossed_below, events, r

SCHEMA_VERSION = 1
MAX_DEPTH = 3  # the top-level group is depth 1
MAX_CONDITIONS = 50  # in the whole definition (buy + sell)
MAX_SHIFT = 100
MAX_BARS = 50
MAX_MULTIPLIER = 1000.0
PRICE_FIELDS = ("open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4")
COMPARE_OPS = (">", "<", ">=", "<=", "crosses_above", "crosses_below")
TREND_OPS = ("rising", "falling")
CATEGORIES = ("trend", "mean_reversion", "breakout", "momentum")
STRENGTHS = ("fixed", "rule_ratio")

_PRICE_INPUTS = {
    "open": ("open",),
    "high": ("high",),
    "low": ("low",),
    "close": ("close",),
    "volume": ("volume",),
    "hl2": ("high", "low"),
    "hlc3": ("high", "low", "close"),
    "ohlc4": ("open", "high", "low", "close"),
}


# --- errors ----------------------------------------------------------------------------------


Loc = Sequence[str | int]


def _is_tag(part: str | int) -> bool:
    return isinstance(part, str) and part.startswith("<")


def format_path(loc: Loc) -> str:
    """``("buy", "all", 2, "right")`` -> ``buy.all[2].right``. Union tags (``<...>``) that
    Pydantic adds to locations are dropped, so paths match the JSON document."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        elif not _is_tag(part):
            out += f".{part}" if out else str(part)
    return out


def issue(loc: Loc, message: str) -> dict[str, Any]:
    """``{"path": "buy.all[2].right", "loc": ["buy", "all", 2, "right"], "message"}``."""
    return {
        "path": format_path(loc),
        "loc": [p for p in loc if not _is_tag(p)],
        "message": message,
    }


class DefinitionError(ValueError):
    """An invalid definition. ``errors`` lists ``{"path", "message"}`` with JSON paths such as
    ``buy.all[2].right.params.length`` (and ``loc``, the same as a list); ``str()`` joins them as
    ``path: message``."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(
            "; ".join(f"{e['path']}: {e['message']}" if e["path"] else e["message"] for e in errors)
        )


def pydantic_issues(exc: ValidationError, prefix: Loc = ()) -> list[dict[str, Any]]:
    return [
        issue((*prefix, *e["loc"]), e["msg"].removeprefix("Value error, "))
        for e in exc.errors(include_url=False)
    ]


# --- the document model (structure only; registry rules are checked afterwards) ---------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Shift = Annotated[
    int, Field(default=0, ge=0, le=MAX_SHIFT, strict=True, description="value n bars ago")
]
Multiplier = Annotated[
    float,
    Field(
        default=1.0,
        gt=0,
        le=MAX_MULTIPLIER,
        allow_inf_nan=False,
        description="the operand's value times this number (e.g. 1.5 x volume SMA)",
    ),
]


class IndicatorOperand(_Strict):
    type: Literal["indicator"]
    name: str = Field(min_length=1, max_length=32, description="an indicator of the catalog")
    params: dict[str, Any] = Field(default_factory=dict, description="omitted = default")
    output: str | None = Field(
        default=None, description="required when the indicator has several outputs"
    )
    shift: Shift = 0
    multiplier: Multiplier = 1.0


class PriceOperand(_Strict):
    type: Literal["price"]
    field: Literal["open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"]
    shift: Shift = 0
    multiplier: Multiplier = 1.0


class ConstantOperand(_Strict):
    type: Literal["constant"]
    value: float = Field(allow_inf_nan=False)
    shift: Shift = 0

    @field_validator("value", mode="before")
    @classmethod
    def _number(cls, v: Any) -> Any:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("must be a number")
        return v


def _get(v: Any, key: str) -> Any:
    return v.get(key) if isinstance(v, dict) else getattr(v, key, None)


def _operand_tag(v: Any) -> str | None:
    kind = _get(v, "type")
    return f"<{kind}>" if isinstance(kind, str) else None


Operand = Annotated[
    Union[  # noqa: UP007 - Annotated tagged union members
        Annotated[IndicatorOperand, Tag("<indicator>")],
        Annotated[PriceOperand, Tag("<price>")],
        Annotated[ConstantOperand, Tag("<constant>")],
    ],
    Discriminator(
        _operand_tag,
        custom_error_type="operand_type",
        custom_error_message="an operand needs 'type': 'indicator', 'price' or 'constant'",
    ),
]


class CompareCondition(_Strict):
    left: Operand
    op: Literal[">", "<", ">=", "<=", "crosses_above", "crosses_below"]
    right: Operand


class BetweenCondition(_Strict):
    op: Literal["between"]
    value: Operand
    lower: Operand
    upper: Operand


class TrendCondition(_Strict):
    op: Literal["rising", "falling"]
    value: Operand
    bars: int = Field(ge=1, le=MAX_BARS, strict=True)


class AllGroup(_Strict):
    all: list[Node] = Field(min_length=1, description="AND: every child is true")


class AnyGroup(_Strict):
    any: list[Node] = Field(min_length=1, description="OR: at least one child is true")


def _node_tag(v: Any) -> str | None:
    if isinstance(v, AllGroup) or (isinstance(v, dict) and "all" in v):
        return "<all>"
    if isinstance(v, AnyGroup) or (isinstance(v, dict) and "any" in v):
        return "<any>"
    if not isinstance(v, (dict, BaseModel)):
        return None
    op = _get(v, "op")
    if op == "between":
        return "<between>"
    if op in TREND_OPS:
        return "<trend>"
    if op is not None:  # a comparison, or an unknown op reported by the comparison model
        return "<compare>"
    return None


NODE_ERROR = (
    "expected a condition with 'op' (>, <, >=, <=, crosses_above, crosses_below, between, "
    "rising, falling) or a group {'all': [...]} / {'any': [...]}"
)
Node = Annotated[
    Union[  # noqa: UP007
        Annotated[AllGroup, Tag("<all>")],
        Annotated[AnyGroup, Tag("<any>")],
        Annotated[CompareCondition, Tag("<compare>")],
        Annotated[BetweenCondition, Tag("<between>")],
        Annotated[TrendCondition, Tag("<trend>")],
    ],
    Discriminator(_node_tag, custom_error_type="node", custom_error_message=NODE_ERROR),
]
Group = Annotated[
    Union[  # noqa: UP007
        Annotated[AllGroup, Tag("<all>")],
        Annotated[AnyGroup, Tag("<any>")],
    ],
    Discriminator(
        lambda v: t if (t := _node_tag(v)) in ("<all>", "<any>") else None,
        custom_error_type="group",
        custom_error_message="must be a group: {'all': [...]} or {'any': [...]}",
    ),
]
AllGroup.model_rebuild()
AnyGroup.model_rebuild()


class BuilderDefinition(_Strict):
    """A Builder strategy (see the module docstring for the semantics)."""

    schema_version: Literal[1]
    buy: Group | None = None
    sell: Group | None = None
    strength: Literal["fixed", "rule_ratio"] = "fixed"
    category: Literal["trend", "mean_reversion", "breakout", "momentum"]


# --- validation and normalisation --------------------------------------------------------------


class _Checker:
    """Registry rules, limits and normalisation of a structurally valid definition."""

    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.conditions = 0

    def operand(self, op: Any, loc: Loc) -> dict[str, Any]:
        if isinstance(op, PriceOperand):
            return {
                "type": "price",
                "field": op.field,
                "shift": op.shift,
                "multiplier": float(op.multiplier),
            }
        if isinstance(op, ConstantOperand):
            return {"type": "constant", "value": float(op.value), "shift": op.shift}
        return self.indicator(op, loc)

    def indicator(self, op: IndicatorOperand, loc: Loc) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": "indicator",
            "name": op.name,
            "params": dict(op.params),
            "output": op.output,
            "shift": op.shift,
            "multiplier": float(op.multiplier),
        }
        spec = ti.INDICATORS.get(op.name)
        if spec is None:
            available = ", ".join(sorted(ti.INDICATORS))
            self.errors.append(
                issue((*loc, "name"), f"unknown indicator {op.name!r} (available: {available})")
            )
            return out
        known = {p.name: p for p in spec.params}
        params_ok = True
        for name, value in op.params.items():
            if name not in known:
                allowed = ", ".join(known) or "none"
                self.errors.append(
                    issue(
                        (*loc, "params", name),
                        f"unknown parameter of {op.name} (allowed: {allowed})",
                    )
                )
                params_ok = False
                continue
            try:
                known[name].validate(value)
            except ValueError as exc:
                self.errors.append(issue((*loc, "params", name), str(exc)))
                params_ok = False
        if params_ok:
            try:
                out["params"] = spec.resolve(op.params)
            except ValueError as exc:  # cross-parameter rules (macd fast < slow)
                self.errors.append(issue((*loc, "params"), str(exc)))
        outputs = spec.outputs
        if op.output is None:
            if len(outputs) > 1:
                self.errors.append(
                    issue(
                        (*loc, "output"),
                        f"required: {op.name} has several outputs ({', '.join(outputs)})",
                    )
                )
            else:
                out["output"] = outputs[0]
        elif op.output not in outputs:
            self.errors.append(
                issue(
                    (*loc, "output"),
                    f"{op.name} has no output {op.output!r} (outputs: {', '.join(outputs)})",
                )
            )
        return out

    def node(self, node: Any, loc: Loc, depth: int) -> dict[str, Any]:
        if isinstance(node, (AllGroup, AnyGroup)):
            kind = "all" if isinstance(node, AllGroup) else "any"
            if depth > MAX_DEPTH:
                self.errors.append(
                    issue(loc, f"groups can be nested at most {MAX_DEPTH} levels deep")
                )
                return {kind: []}
            children = getattr(node, kind)
            return {
                kind: [self.node(c, (*loc, kind, i), depth + 1) for i, c in enumerate(children)]
            }
        self.conditions += 1
        if isinstance(node, CompareCondition):
            return {
                "left": self.operand(node.left, (*loc, "left")),
                "op": node.op,
                "right": self.operand(node.right, (*loc, "right")),
            }
        if isinstance(node, BetweenCondition):
            return {
                "op": "between",
                "value": self.operand(node.value, (*loc, "value")),
                "lower": self.operand(node.lower, (*loc, "lower")),
                "upper": self.operand(node.upper, (*loc, "upper")),
            }
        return {
            "op": node.op,
            "value": self.operand(node.value, (*loc, "value")),
            "bars": node.bars,
        }


def builder_errors(definition: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """``(normalised definition, [])`` or ``(None, errors)``."""
    try:
        model = BuilderDefinition.model_validate(definition)
    except ValidationError as exc:
        return None, pydantic_issues(exc)
    checker = _Checker()
    out: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    if model.buy is None and model.sell is None:
        checker.errors.append(issue((), "give buy and/or sell rules"))
    for side in ("buy", "sell"):
        group = getattr(model, side)
        out[side] = None if group is None else checker.node(group, (side,), 1)
    out["strength"] = model.strength
    out["category"] = model.category
    if checker.conditions > MAX_CONDITIONS:
        checker.errors.append(
            issue((), f"at most {MAX_CONDITIONS} conditions, got {checker.conditions}")
        )
    if checker.errors:
        return None, checker.errors
    return out, []


def validate_builder(definition: Any) -> dict[str, Any]:
    """The normalised definition (indicator params resolved with defaults, single outputs and
    shifts made explicit), or :class:`DefinitionError`."""
    normalised, errors = builder_errors(definition)
    if errors:
        raise DefinitionError(errors)
    assert normalised is not None
    return normalised


# --- walking a normalised definition -----------------------------------------------------------


def _walk(node: Mapping[str, Any]):
    """Every condition under ``node`` (groups are descended)."""
    for kind in ("all", "any"):
        if kind in node:
            for child in node[kind]:
                yield from _walk(child)
            return
    yield node


def _operands(cond: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [cond[k] for k in ("left", "right", "value", "lower", "upper") if k in cond]


def _conditions(definition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [c for side in ("buy", "sell") if definition[side] for c in _walk(definition[side])]


def _indicator_key(op: Mapping[str, Any]) -> tuple[str, str]:
    return op["name"], json.dumps(op["params"], sort_keys=True)


# --- evaluation --------------------------------------------------------------------------------


def _shift(x: np.ndarray, n: int) -> np.ndarray:
    if n == 0:
        return x
    out = np.full(len(x), np.nan)
    if n < len(x):
        out[n:] = x[:-n]
    return out


class _Evaluator:
    """Computes each distinct indicator (name + params) and operand once."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.n = len(df)
        self._indicators: dict[tuple[str, str], pd.DataFrame] = {}
        self._operands: dict[str, np.ndarray] = {}
        # id() of operand dicts of the definition, which lives longer than this evaluator
        self._by_id: dict[int, np.ndarray] = {}

    def _column(self, name: str) -> np.ndarray:
        return self.df[name].to_numpy(dtype=np.float64)

    def operand(self, op: Mapping[str, Any]) -> np.ndarray:
        seen = self._by_id.get(id(op))  # the same dict again (details of every signal bar)
        if seen is not None:
            return seen
        key = json.dumps(op, sort_keys=True)  # an equal operand elsewhere in the definition
        cached = self._operands.get(key)
        if cached is not None:
            self._by_id[id(op)] = cached
            return cached
        kind = op["type"]
        if kind == "constant":
            base = np.full(self.n, float(op["value"]))
        elif kind == "price":
            field = op["field"]
            if field == "hl2":
                base = (self._column("high") + self._column("low")) / 2
            elif field == "hlc3":
                base = (self._column("high") + self._column("low") + self._column("close")) / 3
            elif field == "ohlc4":
                cols = ("open", "high", "low", "close")
                base = sum(self._column(c) for c in cols) / 4
            else:
                base = self._column(field)
        else:
            ikey = _indicator_key(op)
            frame = self._indicators.get(ikey)
            if frame is None:
                frame = ti.compute(op["name"], self.df, **op["params"])
                self._indicators[ikey] = frame
            base = frame[op["output"]].to_numpy(dtype=np.float64)
        value = _shift(base, op["shift"])
        multiplier = op.get("multiplier", 1.0)
        if multiplier != 1.0:
            value = value * multiplier
        self._operands[key] = self._by_id[id(op)] = value
        return value

    def condition(self, cond: Mapping[str, Any]) -> np.ndarray:
        op = cond["op"]
        with np.errstate(invalid="ignore"):
            if op in TREND_OPS:
                v = self.operand(cond["value"])
                ok = np.ones(self.n, dtype=bool)
                for k in range(cond["bars"]):
                    now, before = _shift(v, k), _shift(v, k + 1)
                    ok &= (now > before) if op == "rising" else (now < before)
                return ok
            if op == "between":
                v = self.operand(cond["value"])
                return (v >= self.operand(cond["lower"])) & (v <= self.operand(cond["upper"]))
            a, b = self.operand(cond["left"]), self.operand(cond["right"])
            if op == ">":
                return a > b
            if op == "<":
                return a < b
            if op == ">=":
                return a >= b
            if op == "<=":
                return a <= b
            if op == "crosses_above":
                return crossed_above(a, b)
            return crossed_below(a, b)

    def node(self, node: Mapping[str, Any]) -> np.ndarray:
        if "all" in node:
            out = np.ones(self.n, dtype=bool)
            for child in node["all"]:
                out &= self.node(child)
            return out
        if "any" in node:
            out = np.zeros(self.n, dtype=bool)
            for child in node["any"]:
                out |= self.node(child)
            return out
        return self.condition(node)


def edge(x: np.ndarray) -> np.ndarray:
    """True where ``x`` becomes true after being false (the bar before the data counts as
    false)."""
    prev = np.zeros(len(x), dtype=bool)
    prev[1:] = x[:-1]
    return x & ~prev


def _describe_child(ev: _Evaluator, child: Mapping[str, Any], truth: bool, t: int) -> dict:
    if "all" in child or "any" in child:
        return {"group": "all" if "all" in child else "any", "true": truth}
    op = child["op"]
    out: dict[str, Any] = {"op": op, "true": truth}
    if op in TREND_OPS:
        v = ev.operand(child["value"])
        start = t - child["bars"]
        out.update(value=r(v[t]), value_start=r(v[start]) if start >= 0 else None)
        out["bars"] = child["bars"]
    elif op == "between":
        for k in ("value", "lower", "upper"):
            out[k] = r(ev.operand(child[k])[t])
    else:
        a, b = ev.operand(child["left"]), ev.operand(child["right"])
        out.update(left=r(a[t]), right=r(b[t]))
        if op.startswith("crosses"):
            out.update(
                left_prev=r(a[t - 1]) if t > 0 else None,
                right_prev=r(b[t - 1]) if t > 0 else None,
            )
    return out


class BuilderStrategy(Strategy):
    """A strategy built from a Builder definition; ``generate()`` and ``history()`` behave like
    the global strategies'. It takes no parameters (``params`` must be empty)."""

    params = ()

    def __init__(
        self,
        definition: Mapping[str, Any],
        *,
        key: str = "builder",
        title: str = "Custom strategy",
        description: str = "",
    ) -> None:
        self.definition = validate_builder(definition)
        self.key = key
        self.title = title
        self.description = description
        self.category = self.definition["category"]
        conditions = _conditions(self.definition)
        operands = [op for c in conditions for op in _operands(c)]
        seen: dict[tuple[str, str], dict[str, Any]] = {}
        columns: set[str] = set()
        for op in operands:
            if op["type"] == "indicator":
                seen.setdefault(
                    _indicator_key(op), {"name": op["name"], "params": dict(op["params"])}
                )
                columns.update(ti.get_indicator(op["name"]).inputs)
            elif op["type"] == "price":
                columns.update(_PRICE_INPUTS[op["field"]])
        self._indicators = list(seen.values())
        self.inputs = tuple(c for c in ti.core.OHLCV if c in columns)
        warmup = 0
        for ind in self._indicators:
            spec = ti.get_indicator(ind["name"])
            warmup = max(warmup, spec.lookback(ind["params"]) + spec.convergence(ind["params"]))
        max_shift = max((op["shift"] for op in operands), default=0)
        look_back = 0
        for c in conditions:
            if c["op"] in TREND_OPS:
                look_back = max(look_back, c["bars"])
            elif c["op"].startswith("crosses"):
                look_back = max(look_back, 1)
        # + 1: the edge compares with the previous bar's rules; + 1: bars, not an index
        self._history = warmup + max_shift + look_back + 2

    def indicators(self, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [dict(i, params=dict(i["params"])) for i in self._indicators]

    def history(self, params: Mapping[str, Any] | None = None) -> int:
        """Indicator warm-up (lookback + convergence) + the largest ``shift`` + the largest
        look-back of an op (``bars`` of rising/falling, 1 for crosses) + 1 bar for the edge
        trigger + 1."""
        self.resolve(params)
        return self._history

    def _side(self, ev: _Evaluator, side: str) -> tuple[np.ndarray, list[np.ndarray]]:
        group = self.definition[side]
        if group is None:
            return np.zeros(ev.n, dtype=bool), []
        kind = "all" if "all" in group else "any"
        children = [ev.node(c) for c in group[kind]]
        tree = np.logical_and.reduce(children) if kind == "all" else np.logical_or.reduce(children)
        return tree, children

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        ev = _Evaluator(df)
        buy_tree, buy_children = self._side(ev, "buy")
        sell_tree, sell_children = self._side(ev, "sell")
        buy, sell = edge(buy_tree), edge(sell_tree)
        conflict = buy & sell
        buy, sell = buy & ~conflict, sell & ~conflict

        def describe(t: int, side: int):
            name = "buy" if side == BUY else "sell"
            group = self.definition[name]
            kind = "all" if "all" in group else "any"
            arrays = buy_children if side == BUY else sell_children
            truths = [bool(a[t]) for a in arrays]
            ratio = sum(truths) / len(truths)
            strength = 1.0 if self.definition["strength"] == "fixed" else ratio
            details = {
                "rules": kind,
                "true": sum(truths),
                "total": len(truths),
                "conditions": [
                    _describe_child(ev, c, truth, t)
                    for c, truth in zip(group[kind], truths, strict=True)
                ],
            }
            return strength, f"builder_{name}", details

        return events(df.index, buy, sell, describe)
