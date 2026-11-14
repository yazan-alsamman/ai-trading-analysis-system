"""The strategy registry (``docs/phase7/PLAN.md``, "Built for more strategies").

Each served strategy is one ``Entry``: an id, a version, its exit type, the level kinds it trades,
and a plain-language description in Arabic and English (``descriptions/<id>.<lang>.md``) that the
explanation template and the LLM read. A strategy enters the registry only after it passed its
research (registration, test, unseen data); the registry adds no rule of its own."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

DESCRIPTIONS = Path(__file__).resolve().parent / "descriptions"
ExitType = Literal["target", "trailing", "time"]


@dataclass(frozen=True)
class Entry:
    id: str
    version: str
    exit_type: ExitType
    kinds: dict[str, tuple[str, str]]  # level kind -> (label_ar, label_en)
    doc: str  # where its rules and evidence are recorded

    def description(self, lang: Literal["ar", "en"]) -> str:
        return (DESCRIPTIONS / f"{self.id.lower()}.{lang}.md").read_text(encoding="utf-8")


_V1 = "gold-v1"  # GOLD_V1.md, frozen 2026-11-05; shadows GOLD_SHADOW.md; ROUND GOLD_ROUND.md §6
GOLD_LEVELS: tuple[Entry, ...] = (
    Entry("LVL4H", _V1, "trailing",
          {"PDH": ("قمة اليوم السابق", "previous day's high"),
           "PDL": ("قاع اليوم السابق", "previous day's low"),
           "5DH": ("أعلى سعر في آخر خمسة أيام", "five-day high"),
           "5DL": ("أدنى سعر في آخر خمسة أيام", "five-day low")},
          "docs/strategies/GOLD_V1.md"),
    Entry("PIVOT", _V1, "trailing",
          {"R1": ("مقاومة البيفوت اليومي الأولى R1", "daily pivot resistance R1"),
           "S1": ("دعم البيفوت اليومي الأول S1", "daily pivot support S1")},
          "docs/strategies/GOLD_V1.md"),
    Entry("PIVW", _V1, "trailing",
          {"R1": ("مقاومة البيفوت اليومي الأولى R1", "daily pivot resistance R1"),
           "S1": ("دعم البيفوت اليومي الأول S1", "daily pivot support S1")},
          "docs/strategies/GOLD_SHADOW.md"),
    Entry("ASIA", _V1, "trailing",
          {"ASH": ("قمة الجلسة الآسيوية", "Asian session high"),
           "ASL": ("قاع الجلسة الآسيوية", "Asian session low")},
          "docs/strategies/GOLD_SHADOW.md"),
    Entry("PWHL", _V1, "trailing",
          {"PWH": ("قمة الأسبوع السابق", "previous week's high"),
           "PWL": ("قاع الأسبوع السابق", "previous week's low")},
          "docs/strategies/GOLD_SHADOW.md"),
    Entry("ROUND", _V1, "trailing",
          {"RU": ("الرقم المستدير (مضاعف 50 دولاراً) فوق إغلاق الأمس",
                  "the round number ($50 multiple) above yesterday's close"),
           "RD": ("الرقم المستدير (مضاعف 50 دولاراً) تحت إغلاق الأمس",
                  "the round number ($50 multiple) below yesterday's close")},
          "docs/strategies/GOLD_ROUND.md"),
)  # fmt: skip


@cache
def registry() -> dict[str, Entry]:
    return {e.id: e for e in GOLD_LEVELS}
