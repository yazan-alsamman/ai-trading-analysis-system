"""Deterministic Smart Money Concepts primitives and the Sweep -> CHoCH -> FVG strategy.

Everything here works on closed bars only and is free of look-ahead: a value computed at bar ``j``
uses bars up to and including ``j`` and nothing later. See ``docs/AI_ENGINE_SPEC.md`` (Strategy
definition) for the rules this package implements."""
