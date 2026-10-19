"""Market-data layer: provider adapters, the session calendar, closed-bar aggregation and quality
checks.

Everything here works on a canonical bar frame (see ``schema.CANONICAL_COLUMNS``) with UTC
timestamps. Provider-specific parsing lives in its own module (``mt5``) so other sources can be
added behind the same contract."""
