"""Composite strategies: several strategies (global or custom) voting as one.

Definition (``schema_version`` 1)::

    {
      "schema_version": 1,
      "members": [
        {"ref": "rsi_reversal", "params": {"oversold": 25}, "weight": 1.0},
        {"ref": "custom:<uuid>", "weight": 2.0}
      ],
      "mode": "all" | "any" | "majority" | "weighted",
      "window": 3,
      "threshold": 0.6
    }

* 2-5 members. ``ref`` is a global strategy key or ``custom:<uuid>``; custom definitions come
  from a ``resolver`` callback (the library never touches a database). Custom members take no
  ``params``.
* A member **votes buy** on bar ``t`` if it emitted a buy within the last ``window`` bars
  (``t - window + 1 .. t``) and no sell since; the same for sell.
* ``all``: every member votes the same side. ``any``: at least one votes and none votes the
  other side. ``majority``: more than half vote the same side. ``weighted``: the votes' weight
  divided by the total weight is ``>= threshold``; if both sides reach it, nothing.
* The output is edge-triggered like the Builder's (fires when the agreement starts),
  ``strength`` is the agreement ratio (voting weight / total weight for ``weighted``, voters /
  members otherwise) and ``details`` lists every member's vote.
* Composites may contain composites, at most 3 levels deep; cycles (A -> B -> A) are rejected.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import Field, ValidationError, field_validator

from trading_strategies.base import BUY, SELL, Strategy, events
from trading_strategies.builder import (
    BuilderStrategy,
    DefinitionError,
    Loc,
    _Strict,
    builder_errors,
    edge,
    issue,
    pydantic_issues,
)
from trading_strategies.registry import STRATEGIES

MIN_MEMBERS, MAX_MEMBERS = 2, 5
MAX_WINDOW = 20
MAX_NESTING = 3  # the composite itself is level 1
MODES = ("all", "any", "majority", "weighted")
CUSTOM_PREFIX = "custom:"
CUSTOM_REF = re.compile(
    r"^custom:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

# ref -> (kind, definition) of a custom strategy; raises LookupError when unknown/inaccessible
Resolver = Callable[[str], tuple[str, Mapping[str, Any]]]


def is_custom(ref: str) -> bool:
    return ref.startswith(CUSTOM_PREFIX)


class Member(_Strict):
    ref: str = Field(min_length=1, max_length=64, description="global key or custom:<uuid>")
    params: dict[str, Any] = Field(default_factory=dict, description="global strategies only")
    weight: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)

    @field_validator("ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        if is_custom(v):
            if not CUSTOM_REF.match(v):
                raise ValueError("custom references look like custom:<uuid>")
            return v.lower()
        if v not in STRATEGIES:
            raise ValueError(
                f"unknown strategy {v!r} (global: {', '.join(sorted(STRATEGIES))}, "
                "or custom:<uuid>)"
            )
        return v


class CompositeDefinition(_Strict):
    """A Composite strategy (see the module docstring for the semantics)."""

    schema_version: Literal[1]
    members: list[Member] = Field(min_length=MIN_MEMBERS, max_length=MAX_MEMBERS)
    mode: Literal["all", "any", "majority", "weighted"]
    window: int = Field(default=1, ge=1, le=MAX_WINDOW, strict=True)
    threshold: float = Field(
        default=0.5, gt=0, le=1, allow_inf_nan=False, description="weighted mode only"
    )


class _Resolution:
    """Builds member strategies recursively with nesting and cycle checks, collecting every
    custom definition used (for snapshots)."""

    def __init__(self, resolver: Resolver | None, resolved: dict | None = None) -> None:
        self.resolver = resolver
        self.resolved: dict[str, dict[str, Any]] = {} if resolved is None else resolved
        self.errors: list[dict[str, Any]] = []

    def _nested(self, loc: Loc, ref: str, errors: list[dict[str, Any]]) -> None:
        first = errors[0]
        where = f"{first['path']}: " if first["path"] else ""
        self.errors.append(issue((*loc, "ref"), f"{ref} is invalid: {where}{first['message']}"))

    def custom(self, ref: str, loc: Loc, stack: tuple[str, ...], level: int) -> Strategy | None:
        if ref in stack:
            cycle = " -> ".join((*stack[stack.index(ref) :], ref))
            self.errors.append(issue((*loc, "ref"), f"cycle: {cycle}"))
            return None
        if self.resolver is None:
            self.errors.append(issue((*loc, "ref"), f"cannot resolve {ref} (no resolver)"))
            return None
        try:
            kind, definition = self.resolver(ref)
        except LookupError:
            self.errors.append(issue((*loc, "ref"), f"unknown or inaccessible strategy {ref}"))
            return None
        if kind == "builder":
            normalised, errors = builder_errors(definition)
            if errors:
                self._nested(loc, ref, errors)
                return None
            self.resolved[ref] = {"kind": "builder", "definition": normalised}
            return BuilderStrategy(normalised, key=ref, title=ref)
        if kind != "composite":
            self.errors.append(issue((*loc, "ref"), f"{ref} has an unknown kind {kind!r}"))
            return None
        if level + 1 > MAX_NESTING:
            self.errors.append(
                issue((*loc, "ref"), f"composites can be nested at most {MAX_NESTING} levels deep")
            )
            return None
        sub = _Resolution(self.resolver, self.resolved)
        built = sub.composite(definition, (*stack, ref), level + 1)
        if built is None or sub.errors:
            self._nested(loc, ref, sub.errors)
            return None
        model, members = built
        self.resolved[ref] = {"kind": "composite", "definition": _dump(model)}
        return CompositeStrategy._from_parts(model, members, key=ref, title=ref)

    def composite(
        self, definition: Any, stack: tuple[str, ...], level: int
    ) -> tuple[CompositeDefinition, list[tuple[Member, Strategy, dict[str, Any]]]] | None:
        try:
            model = CompositeDefinition.model_validate(definition)
        except ValidationError as exc:
            self.errors.extend(pydantic_issues(exc))
            return None
        members: list[tuple[Member, Strategy, dict[str, Any]]] = []
        for i, member in enumerate(model.members):
            loc = ("members", i)
            if is_custom(member.ref):
                if member.params:
                    self.errors.append(issue((*loc, "params"), "custom strategies take no params"))
                    continue
                strategy = self.custom(member.ref, loc, stack, level)
                if strategy is not None:
                    members.append((member, strategy, {}))
                continue
            strategy = STRATEGIES[member.ref]
            try:
                params = strategy.resolve(member.params)
            except ValueError as exc:
                self.errors.append(issue((*loc, "params"), str(exc)))
                continue
            members.append((member, strategy, params))
        return model, members


def _dump(model: CompositeDefinition) -> dict[str, Any]:
    """Normalised composite definition (defaults explicit, global params resolved)."""
    members = []
    for m in model.members:
        params = {} if is_custom(m.ref) else STRATEGIES[m.ref].resolve(m.params)
        members.append({"ref": m.ref, "params": params, "weight": float(m.weight)})
    return {
        "schema_version": 1,
        "members": members,
        "mode": model.mode,
        "window": model.window,
        "threshold": float(model.threshold),
    }


def composite_errors(
    definition: Any, resolver: Resolver | None = None, *, ref: str | None = None
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """``(normalised definition, errors, resolved custom members)``; ``ref`` is the
    composite's own key (``custom:<uuid>``) when it has one, for cycle detection."""
    res = _Resolution(resolver)
    built = res.composite(definition, (ref,) if ref else (), 1)
    if built is None or res.errors:
        return None, res.errors, {}
    return _dump(built[0]), [], res.resolved


def votes(signal: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """(votes buy, votes sell): the member emitted that side within the last ``window`` bars
    and not the other side since."""
    n = len(signal)
    idx = np.arange(n)
    last_buy = np.maximum.accumulate(np.where(signal == BUY, idx, -1))
    last_sell = np.maximum.accumulate(np.where(signal == SELL, idx, -1))
    buy = (last_buy >= 0) & (idx - last_buy < window) & (last_sell < last_buy)
    sell = (last_sell >= 0) & (idx - last_sell < window) & (last_buy < last_sell)
    return buy, sell


class CompositeStrategy(Strategy):
    """A strategy voting with its members; takes no parameters of its own."""

    params = ()
    inputs = ()

    def __init__(
        self,
        definition: Mapping[str, Any],
        resolver: Resolver | None = None,
        *,
        key: str = "composite",
        title: str = "Custom composite",
        description: str = "",
    ) -> None:
        res = _Resolution(resolver)
        built = res.composite(definition, (key,) if is_custom(key) else (), 1)
        if built is None or res.errors:
            raise DefinitionError(res.errors)
        self._setup(*built, key=key, title=title, description=description)
        self.resolved = res.resolved

    @classmethod
    def _from_parts(cls, model, members, *, key: str, title: str) -> CompositeStrategy:
        self = cls.__new__(cls)
        self._setup(model, members, key=key, title=title, description="")
        self.resolved = {}
        return self

    def _setup(self, model, members, *, key: str, title: str, description: str) -> None:
        self.definition = _dump(model)
        self.members = [(m.ref, s, p, float(m.weight)) for m, s, p in members]
        self.key, self.title, self.description = key, title, description
        # the category of the heaviest member (first on ties)
        self.category = max(self.members, key=lambda m: m[3])[1].category
        columns = {c for _, s, _, _ in self.members for c in s.inputs}
        self.inputs = tuple(c for c in ("open", "high", "low", "close", "volume") if c in columns)

    def indicators(self, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        out, seen = [], set()
        for _, strategy, member_params, _ in self.members:
            for ind in strategy.indicators(member_params):
                key = (ind["name"], tuple(sorted(ind["params"].items())))
                if key not in seen:
                    seen.add(key)
                    out.append(ind)
        return out

    def history(self, params: Mapping[str, Any] | None = None) -> int:
        """The largest member history + ``window``."""
        self.resolve(params)
        longest = max(s.history(p) for _, s, p, _ in self.members)
        return longest + self.definition["window"]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        window, mode = self.definition["window"], self.definition["mode"]
        weights = np.array([m[3] for m in self.members])
        total = weights.sum()
        buy_votes, sell_votes = [], []
        for _, strategy, params, _ in self.members:
            sig = strategy.generate(df, params)["signal"].to_numpy()
            b, s = votes(sig, window)
            buy_votes.append(b)
            sell_votes.append(s)
        vb, vs = np.vstack(buy_votes), np.vstack(sell_votes)
        n_members = len(self.members)
        nb, ns = vb.sum(axis=0), vs.sum(axis=0)
        if mode == "weighted":
            ratio_b, ratio_s = (weights @ vb) / total, (weights @ vs) / total
        else:
            ratio_b, ratio_s = nb / n_members, ns / n_members
        if mode == "all":
            want_b, want_s = nb == n_members, ns == n_members
        elif mode == "any":
            want_b, want_s = (nb > 0) & (ns == 0), (ns > 0) & (nb == 0)
        elif mode == "majority":
            want_b, want_s = nb * 2 > n_members, ns * 2 > n_members
        else:
            threshold = self.definition["threshold"] - 1e-12  # float sums of weights
            want_b, want_s = ratio_b >= threshold, ratio_s >= threshold
            both = want_b & want_s
            want_b, want_s = want_b & ~both, want_s & ~both
        buy, sell = edge(want_b), edge(want_s)

        def describe(t: int, side: int):
            members = []
            for i, (ref, _, _, weight) in enumerate(self.members):
                vote = "buy" if vb[i, t] else "sell" if vs[i, t] else None
                members.append({"ref": ref, "weight": weight, "vote": vote})
            ratio = ratio_b[t] if side == BUY else ratio_s[t]
            details = {
                "mode": mode,
                "window": window,
                "agreement": round(float(ratio), 6),
                "members": members,
            }
            return float(ratio), "composite_buy" if side == BUY else "composite_sell", details

        return events(df.index, buy, sell, describe)
