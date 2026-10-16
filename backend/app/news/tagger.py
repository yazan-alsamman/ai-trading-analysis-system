"""The built-in instrument tagger: symbols and names in the title or summary (see aliases.py)."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument, MarketType
from app.news.aliases import ALIASES, SUMMARY_RELEVANCE, TITLE_RELEVANCE

_AR = "\u0600-\u06ff"


def _pattern(codes, names, arabic) -> re.Pattern[str] | None:
    parts = []
    if codes:
        alternatives = "|".join(re.escape(c) for c in codes)
        parts.append(f"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])")
    if names:
        alternatives = "|".join(re.escape(n) for n in names)
        parts.append(f"(?i:\\b(?:{alternatives})s?\\b)")
    if arabic:
        alternatives = "|".join(re.escape(a) for a in arabic)
        # Arabic words take the article "ال" and one-letter prefixes (و، ب، ف، ل), which \b
        # does not separate: "البيتكوين", "وبيتكوين", "والذهب"
        parts.append(f"(?<![{_AR}])(?:[وبفل]?ال|[وبفل])?(?:{alternatives})(?![{_AR}])")
    return re.compile("|".join(parts)) if parts else None


@dataclass(frozen=True)
class Tagger:
    rules: tuple[tuple[uuid.UUID, re.Pattern[str]], ...]

    @classmethod
    def build(cls, instruments: list[tuple[uuid.UUID, str, str, MarketType]]) -> "Tagger":
        """``instruments``: (id, symbol, base asset, market) of the active instruments."""
        rules = []
        for iid, symbol, base, market in instruments:
            entry = ALIASES.get(symbol)
            if entry is not None:
                pattern = _pattern(entry["codes"], entry["names"], entry["ar"])
            elif market == MarketType.crypto and len(base) >= 3:
                pattern = _pattern((base.upper(),), (), ())
            else:
                pattern = None
            if pattern is not None:
                rules.append((iid, pattern))
        return cls(tuple(rules))

    @classmethod
    async def load(cls, session: AsyncSession) -> "Tagger":
        rows = await session.execute(
            select(
                Instrument.id, Instrument.symbol, Instrument.base_asset, Instrument.market
            ).where(Instrument.is_active.is_(True))
        )
        return cls.build([tuple(r) for r in rows.all()])

    def tag(self, title: str, summary: str | None) -> dict[uuid.UUID, float]:
        """instrument id -> relevance (1.0 in the title, 0.6 only in the summary)."""
        out: dict[uuid.UUID, float] = {}
        for iid, pattern in self.rules:
            if pattern.search(title):
                out[iid] = TITLE_RELEVANCE
            elif summary and pattern.search(summary):
                out[iid] = SUMMARY_RELEVANCE
        return out
