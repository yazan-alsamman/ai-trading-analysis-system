"""``POST /v1/explain``: the fixed template (P7 F2, ``docs/phase7/PLAN.md``).

The template is filled only with the setup's own fields, its evidence and its strategy's
description, in Arabic (formal, as the contract's example) or English. Every text goes through the
number checker (``app.agent.verify``); a template always passes it, so the answer is
``verified: true, template_used: true`` (contract §9: shown to the user). F3 adds the LLM text in
front of this, with the template as its fallback.

Three templates: the registry's strategies (``evidence.strategy``: the gold levels), the L1 SMC
setups of the ``intraday`` profile (marked unvalidated: the research found no edge), and a plain
one for anything else."""

from __future__ import annotations

from typing import Any, Literal

from app.agent.verify import unverified
from app.catalog import registry
from app.contract import ExplainRequest, ExplainResponse

Lang = Literal["ar", "en"]
DIR = {"ar": {"buy": "شراء", "sell": "بيع"}, "en": {"buy": "buy", "sell": "sell"}}
VOL_LEVEL = {
    "ar": {"quiet": "هادئ", "normal": "عادي", "lively": "نشِط", "very_lively": "نشِط جداً"},
    "en": {"quiet": "quiet", "normal": "normal", "lively": "lively", "very_lively": "very lively"},
}
EXIT = {
    "ar": {
        "stop": "عند وقف الخسارة",
        "trailing_stop": "عند الوقف المتحرك",
        "time": "عند نهاية الوقت",
        "tp": "عند الهدف",
        "sl": "عند وقف الخسارة",
        "timeout": "عند نهاية المدة",
    },
    "en": {
        "stop": "at the stop",
        "trailing_stop": "at the trailing stop",
        "time": "at the time limit",
        "tp": "at the target",
        "sl": "at the stop",
        "timeout": "at the time limit",
    },
}
NOT_ADVICE = {
    "ar": "هذه معلومات عن قاعدة، وليست نصيحة بالتداول.",
    "en": "This is information about a rule, not advice to trade.",
}
SMALL_EDGE = {
    "ar": "الأفضلية التي قاسها البحث صغيرة، وتظهر في عدد كبير من الصفقات لا في صفقة واحدة.",
    "en": "The edge the research measured is small: it shows over many trades, not in one.",
}
UNVALIDATED = {
    "ar": "تنبيه: لم يُثبت البحث أن لهذا النموذج أفضلية بعد احتساب التكاليف، ويُعرض للمعلومة فقط.",
    "en": "Note: the research did not find an edge for this pattern after costs; it is shown for "
    "information only.",
}


def p2(x: float) -> str:
    return f"{float(x):.2f}"


def fact(ev: dict, key: str) -> dict | None:
    return next((f for f in ev.get("facts", []) if f.get("key") == key), None)


def volatility_line(vol: dict | None, lang: Lang) -> str:
    if not vol or vol.get("status") != "ok":
        return ""
    lvl = VOL_LEVEL[lang].get(vol.get("level") or "", "")
    pct, r = vol["expected_move_pct"], vol["range_usd"]
    if lang == "ar":
        line = (
            f"تقلّب اليوم المتوقع {lvl}: حركة نحو {p2(pct)}% ومدى مرجّح نحو {p2(r['p50'])} "
            f"دولار (بين {p2(r['p20'])} و{p2(r['p80'])})."
        )
    else:
        line = (
            f"Today's expected volatility is {lvl}: a move of about {p2(pct)}% and a likely "
            f"range of about ${p2(r['p50'])} (between ${p2(r['p20'])} and ${p2(r['p80'])})."
        )
    news = vol.get("news") or []
    if news:
        items = []
        for n in news:
            when = n.get("ts_ny") or n["ts"]
            top = (" (خبر رئيسي)" if lang == "ar" else " (major)") if n.get("top3") else ""
            items.append(f"{n['title']}{top} {'الساعة' if lang == 'ar' else 'at'} {when}")
        head = (
            "أخبار اليوم المهمة بتوقيت نيويورك: "
            if lang == "ar"
            else "Today's key news, New York time: "
        )
        line += " " + head + ("، " if lang == "ar" else "; ").join(items) + "."
    return line


# --- the registry's strategies (the gold levels) -----------------------------------------------


def level_text(s: dict, lang: Lang) -> str:
    ev = s["evidence"]
    name, state, d = ev["strategy"], s["state"], ev["d"]
    kind = fact(ev, "level_kind") or {}
    price = fact(ev, "level_price") or {}
    label = kind.get(f"label_{lang}", kind.get("value", ""))
    w0, w1 = ev["window_ny"].split("-")
    di = DIR[lang][s["direction"]]
    en_, rr = p2(s["entry"]), p2(s.get("realized_r") or 0)
    why_ar, why_en = (
        EXIT["ar"].get(s.get("exit_reason"), ""),
        EXIT["en"].get(s.get("exit_reason"), ""),
    )
    swing = (
        ("قاع مؤكد" if s["direction"] == "buy" else "قمة مؤكدة")
        if lang == "ar"
        else ("low" if s["direction"] == "buy" else "high")
    )
    if lang == "ar":
        head = {
            "ARMED": f"{name}: أمر {di} معلّق (stop) عند {label} على سعر {en_}، يُنفَّذ "
            f"إذا وصل السعر إلى المستوى بين {w0} و{w1} بتوقيت نيويورك.",
            "ACTIVE": f"{name}: صفقة {di} مفتوحة بعد كسر {label}، والدخول عند {en_}.",
            "CLOSED": f"{name}: أُغلقت صفقة {di} على كسر {label} (الدخول {en_}) "
            f"بنتيجة {rr}R {why_ar}.",
            "EXPIRED": f"{name}: انتهت النافذة دون أن يصل السعر إلى {label} "
            f"({p2(price.get('value', s['entry']))})، فلم تُفتح صفقة.",
            "INVALIDATED": f"{name}: وصل السعر إلى {label} لكن لم تُفتح صفقة "
            + (
                "لأن تكلفة التداول تجاوزت الحد المسموح من مسافة الوقف."
                if s.get("state_reason") == "cost_cap"
                else "لأن الاستراتيجية كانت في صفقة أخرى."
            ),
        }.get(state, f"{name}: {di} عند {label}.")
        stop = (
            f"وقف الخسارة الحالي عند {p2(s['sl'])}، والمسافة الأصلية D = {p2(d)} دولار "
            f"({ev['d_rule']})."
        )
        exit_ = (
            f"لا يوجد هدف ثابت: عند ربح مسافة D واحدة ينتقل الوقف إلى سعر الدخول مضافاً إليه "
            f"التكلفة، ثم يلحق آخر {swing} على فريم 5 دقائق، وتُغلق الصفقة على الأكثر "
            f"الساعة {ev['exit_by_ny']} بتوقيت نيويورك."
        )
    else:
        head = {
            "ARMED": f"{name}: a pending {di} stop order at the {label}, {en_}; it fills "
            f"if the price reaches the level between {w0} and {w1} New York time.",
            "ACTIVE": f"{name}: an open {di} trade after the break of the {label}, entry {en_}.",
            "CLOSED": f"{name}: the {di} trade on the break of the {label} (entry {en_}) "
            f"closed {why_en} with {rr}R.",
            "EXPIRED": f"{name}: the window ended without the price reaching the {label} "
            f"({p2(price.get('value', s['entry']))}); no trade.",
            "INVALIDATED": f"{name}: the price reached the {label} but no trade was opened: "
            + (
                "the trading cost was above the allowed share of the stop distance."
                if s.get("state_reason") == "cost_cap"
                else "the strategy was already in another trade."
            ),
        }.get(state, f"{name}: {di} at the {label}.")
        stop = (
            f"The stop is now at {p2(s['sl'])}; the original distance D is ${p2(d)} "
            f"({ev['d_rule']})."
        )
        exit_ = (
            f"No fixed target: after a profit of one D the stop moves to the entry plus costs, "
            f"then trails the last confirmed 5-minute swing {swing}; the trade closes by "
            f"{ev['exit_by_ny']} New York time at the latest."
        )
    parts = [head]
    if state in ("ARMED", "ACTIVE"):
        parts += [stop, exit_]
    parts += [volatility_line(ev.get("volatility"), lang), SMALL_EDGE[lang], NOT_ADVICE[lang]]
    return " ".join(p for p in parts if p)


# --- L1 (intraday profile) ------------------------------------------------------------------------


def l1_text(s: dict, lang: Lang) -> str:
    ev = s["evidence"]
    lv = ev.get("level") or {}
    di = DIR[lang][s["direction"]]
    en_ = p2(s["entry"])
    why_ar, why_en = (
        EXIT["ar"].get(s.get("exit_reason"), ""),
        EXIT["en"].get(s.get("exit_reason"), ""),
    )
    src, side = lv.get("source"), lv.get("side")
    if lang == "ar":
        where = {
            "pd": "قمة اليوم السابق" if side == "high" else "قاع اليوم السابق",
            "1h": "قمة متأرجحة على فريم 1h" if side == "high" else "قاع متأرجح على فريم 1h",
            "4h": "قمة متأرجحة على فريم 4h" if side == "high" else "قاع متأرجح على فريم 4h",
        }.get(src, "مستوى سيولة")
        parts = [
            f"إعداد SMC ({di} على الذهب): الدخول {en_}، وقف الخسارة {p2(s['sl'])}، "
            f"والهدف {p2(s['tp'])}"
            + (f" (عائد {p2(s['r_multiple'])}R)." if s.get("r_multiple") else ".")
        ]
        if lv.get("price") is not None:
            parts.append(
                f"الأساس: سحب السيولة عند {where} ({p2(lv['price'])})"
                + (
                    f" ثم تغيّر في الهيكل (CHoCH) عند {p2(ev['choch_ref_price'])}"
                    if ev.get("choch_ref_price") is not None
                    else ""
                )
                + "."
            )
        fvg = ev.get("fvg")
        if fvg:
            parts.append(f"مع فجوة سعرية عادلة (FVG) بين {p2(fvg['low'])} و{p2(fvg['high'])}.")
        if s["state"] == "CLOSED" and s.get("realized_r") is not None:
            parts.append(f"أُغلق الإعداد {why_ar} بنتيجة {p2(s['realized_r'])}R.")
    else:
        where = {
            "pd": "the previous day's " + ("high" if side == "high" else "low"),
            "1h": f"a 1h swing {side}",
            "4h": f"a 4h swing {side}",
        }.get(src, "a liquidity level")
        parts = [
            f"SMC setup ({di} on gold): entry {en_}, stop {p2(s['sl'])}, target "
            f"{p2(s['tp'])}" + (f" ({p2(s['r_multiple'])}R)." if s.get("r_multiple") else ".")
        ]
        if lv.get("price") is not None:
            parts.append(
                f"Basis: a liquidity sweep of {where} ({p2(lv['price'])})"
                + (
                    f", then a change of character (CHoCH) at {p2(ev['choch_ref_price'])}"
                    if ev.get("choch_ref_price") is not None
                    else ""
                )
                + "."
            )
        fvg = ev.get("fvg")
        if fvg:
            parts.append(f"With a fair value gap (FVG) from {p2(fvg['low'])} to {p2(fvg['high'])}.")
        if s["state"] == "CLOSED" and s.get("realized_r") is not None:
            parts.append(f"It closed {why_en} with {p2(s['realized_r'])}R.")
    parts += [volatility_line(ev.get("volatility"), lang), UNVALIDATED[lang], NOT_ADVICE[lang]]
    return " ".join(p for p in parts if p)


# --- anything else ------------------------------------------------------------------------


def plain_text(s: dict, lang: Lang) -> str:
    di = DIR[lang].get(s.get("direction", ""), s.get("direction", ""))
    bits = []
    for key, ar, en in (
        ("entry", "الدخول", "entry"),
        ("sl", "وقف الخسارة", "stop"),
        ("tp", "الهدف", "target"),
    ):
        if s.get(key) is not None:
            bits.append(f"{ar if lang == 'ar' else en} {p2(s[key])}")
    sep = "، " if lang == "ar" else ", "
    head = f"إعداد {di}: " if lang == "ar" else f"{di.capitalize()} setup: "
    return head + sep.join(bits) + ". " + NOT_ADVICE[lang]


# --- the answer ----------------------------------------------------------------------------------


def template(s: dict, lang: Lang) -> tuple[str, list[str]]:
    """The template text and the sources its numbers may come from."""
    ev = s.get("evidence") or {}
    entry = registry().get(ev.get("strategy", ""))
    if entry is not None:
        return level_text(s, lang), [s, entry.description(lang)]
    if "level" in ev and "plan" in ev:
        return l1_text(s, lang), [s]
    return plain_text(s, lang), [s]


def explain_setup(s: dict[str, Any], lang: Lang) -> dict[str, Any]:
    text, sources = template(s, lang)
    bad = unverified(text, *sources)
    return {"text": text, "verified": not bad, "template_used": True}


def explain(req: ExplainRequest) -> ExplainResponse:
    s = req.setup.model_dump(mode="json")
    return ExplainResponse(**explain_setup(s, req.lang))
