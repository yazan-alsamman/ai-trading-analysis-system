"""Ready-to-show Arabic and English labels of AI data (B13, contract 0.3.0), so the web and
mobile apps need no mapping of their own: the exit rule of a setup without a target, and the
level of the day's expected move."""

from __future__ import annotations

EXIT_LABELS: dict[str, dict[str, str]] = {
    "trailing": {
        "ar": "الخروج: ستوب متحرك، أو الساعة 16:45 نيويورك",
        "en": "Exit: trailing stop, or 16:45 New York",
    },
    "time": {
        "ar": "الخروج: الوقف، أو الساعة 16:45 نيويورك",
        "en": "Exit: stop, or 16:45 New York",
    },
}

LEVEL_LABELS: dict[str, dict[str, str]] = {
    "quiet": {"ar": "هادئ", "en": "Quiet"},
    "normal": {"ar": "عادي", "en": "Normal"},
    "lively": {"ar": "نشِط", "en": "Lively"},
    "very_lively": {"ar": "نشِط جداً", "en": "Very lively"},
}


def exit_label(exit_type: str | None) -> dict[str, str] | None:
    """``{"ar": ..., "en": ...}`` for a setup without a target (``trailing`` or ``time``);
    None for a setup with a target (``target`` or null)."""
    label = EXIT_LABELS.get(exit_type or "")
    return dict(label) if label else None


def level_label(level: str | None) -> dict[str, str] | None:
    """``{"ar": ..., "en": ...}`` of a volatility level; None when unknown or missing."""
    label = LEVEL_LABELS.get(level or "")
    return dict(label) if label else None
