"""The number checker (``docs/phase7/PLAN.md`` F3, "Built for more strategies" 3).

Every number written in an explanation must be a number of the setup it explains (any field,
nested, including the numbers inside its strings: times, dates, rules such as "0.75 x ATR(14, 4h)")
or of that strategy's description. It knows nothing about any one strategy.

A written number matches an allowed value when the value, rounded to the decimals written, equals
it. A whole number written without decimals matches only a whole value, or a value of 1,000 or more
(a price written without its cents). Western and Arabic-Indic digits, the Arabic decimal sign and
thousands separators are read. Signs are ignored (a direction error is not a number error).
Numbers written as words are not seen: the prompt asks for digits."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Token:
    text: str
    value: float
    decimals: int


def tokens(text: str) -> list[Token]:
    """The numbers written in ``text``."""
    out = []
    for m in _NUMBER.finditer(text.translate(_DIGITS)):
        raw = m.group(0).replace(",", "")
        dec = len(raw.split(".")[1]) if "." in raw else 0
        out.append(Token(m.group(0), float(raw), dec))
    return out


def allowed(*sources: Any) -> set[float]:
    """Every number in ``sources``: numeric fields (nested dicts and lists) and the numbers
    written inside their strings."""
    vals: set[float] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, int | float):
            vals.add(float(x))
        elif isinstance(x, str):
            vals.update(t.value for t in tokens(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list | tuple):
            for v in x:
                walk(v)

    for s in sources:
        walk(s)
    return vals


def matches(tok: Token, values: set[float]) -> bool:
    for a in values:
        a = abs(a)
        if round(a, tok.decimals) != tok.value:
            continue
        if tok.decimals or a == int(a) or a >= 1000:
            return True
    return False


def unverified(text: str, *sources: Any) -> list[str]:
    """The numbers of ``text`` that are not in ``sources`` (empty: the text is verified)."""
    vals = allowed(*sources)
    return [t.text for t in tokens(text) if not matches(t, vals)]
