"""Rendering of notifications per channel and language (the texts are in ``messages.py``).

- Inbox / plain text: ``inbox(type, data, lang) -> (title, body)``.
- Telegram: HTML parse mode, every dynamic value escaped.
- Email: subject, plain-text part and HTML part (``dir="rtl"`` for Arabic).
- Push: a short title/body and a ``data`` map of strings for deep links.
"""

from __future__ import annotations

import html
from typing import Any

from app.notifications.templates.messages import CHANNEL_NAMES, TEXTS

LANGUAGES = ("ar", "en")
PUSH_BODY_MAX = 240


def t(lang: str, key: str, **kw: Any) -> str:
    texts = TEXTS.get(lang) or TEXTS["en"]
    template = texts.get(key) or TEXTS["en"][key]
    return template.format(**kw)


def num(value: Any, digits: int = 2) -> str:
    """``12345.678`` -> ``12,345.68``; None -> ``-``."""
    if value is None:
        return "-"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _signed(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):+,.{digits}f}"


# --- content ---------------------------------------------------------------------------------


def _plan_lines(plan: dict[str, Any] | None, lang: str, price_digits: int, qty_digits: int):
    if not plan:
        return [t(lang, "plan.none")]
    if plan.get("invalid_reason"):
        key = f"reason.{plan['invalid_reason']}"
        reason = t(lang, key) if key in TEXTS["en"] else plan["invalid_reason"]
        return [t(lang, "plan.invalid", reason=reason)]
    currency = plan.get("quote_currency") or "USDT"
    lines = [
        t(lang, "plan.header", account=num(plan.get("account_size"), 0), currency=currency),
        t(lang, "plan.entry", entry=num(plan.get("entry_ref"), price_digits)),
    ]
    if plan.get("stop") is not None:
        lines.append(t(lang, "plan.stop", stop=num(plan["stop"], price_digits)))
    for n, target in enumerate(plan.get("targets") or [], start=1):
        lines.append(
            t(
                lang,
                "plan.target",
                n=n,
                price=num(target.get("price"), price_digits),
                r=num(target.get("r"), 1),
                pct=num(target.get("close_pct"), 0),
            )
        )
    lines.append(
        t(
            lang,
            "plan.size",
            qty=num(plan.get("quantity"), qty_digits),
            notional=num(plan.get("notional"), 2),
            currency=currency,
        )
    )
    if plan.get("risk_amount") is not None:
        lines.append(
            t(
                lang,
                "plan.risk",
                risk=num(plan["risk_amount"], 2),
                currency=currency,
                risk_pct=num(plan.get("risk_pct"), 2),
                rr=num(plan.get("rr"), 2),
            )
        )
    return lines


def _signal(data: dict[str, Any], lang: str) -> tuple[str, str]:
    signal = data.get("signal") or {}
    instrument = data.get("instrument") or {}
    price_digits = instrument.get("price_precision")
    price_digits = 2 if price_digits is None else int(price_digits)
    qty_digits = instrument.get("quantity_precision")
    qty_digits = 4 if qty_digits is None else int(qty_digits)
    side = t(lang, f"side.{signal.get('side', 'buy')}")
    title = t(
        lang,
        "signal.title",
        side=side,
        symbol=instrument.get("symbol", "?"),
        timeframe=signal.get("timeframe", ""),
    )
    lines = [
        t(
            lang,
            "signal.strategy",
            strategy=data.get("strategy_name") or signal.get("strategy_key", "?"),
            strength=num(signal.get("strength"), 2),
        ),
        t(lang, "signal.price", price=num(signal.get("price"), price_digits)),
        "",
        *_plan_lines(data.get("plan"), lang, price_digits, qty_digits),
    ]
    return title, "\n".join(lines)


def _backtest(kind: str, data: dict[str, Any], lang: str) -> tuple[str, str]:
    names = {
        "strategy": data.get("strategy_name") or data.get("strategy_key", "?"),
        "symbol": data.get("symbol", "?"),
        "timeframe": data.get("timeframe", ""),
    }
    title = t(lang, f"{kind}.title", **names)
    if kind == "backtest_failed":
        return title, t(lang, "backtest_failed.body", error=data.get("error") or "-")
    m = data.get("metrics") or {}
    body = t(
        lang,
        "backtest_completed.body",
        ret=_signed(m.get("total_return_pct")),
        dd=num(m.get("max_drawdown_pct")),
        sharpe=num(m.get("sharpe")),
        trades=m.get("trades", "-"),
        win=num(m.get("win_rate_pct"), 1),
    )
    return title, body


def _security(data: dict[str, Any], lang: str) -> tuple[str, str]:
    event = data.get("event", "new_login")
    fields = {
        "ip": data.get("ip", "?"),
        "agent": (data.get("user_agent") or "?")[:80],
        "name": data.get("key_name", "?"),
        "prefix": data.get("key_prefix", "?"),
        "minutes": data.get("minutes", "?"),
    }
    return t(lang, f"security.{event}.title"), t(lang, f"security.{event}.body", **fields)


def excerpt(text: str | None, limit: int = 160) -> str:
    """One line of plain-ish text: Markdown markers and whitespace runs removed, cut at a word."""
    flat = " ".join((text or "").replace("#", " ").replace("*", "").replace("`", "").split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit].rsplit(" ", 1)[0] or flat[:limit]
    return cut + "…"


def _new_post(data: dict[str, Any], lang: str) -> tuple[str, str]:
    title = t(
        lang, "new_post.title", author=data.get("author_name", "?"), title=data.get("title", "")
    )
    lines = []
    if data.get("instrument_symbol"):
        direction = data.get("direction")
        lines.append(
            t(
                lang,
                "new_post.instrument",
                symbol=data["instrument_symbol"],
                direction=t(lang, f"direction.{direction}") if direction else "-",
            )
        )
    lines.append(data.get("excerpt") or "")
    return title, "\n".join(x for x in lines if x)


def _comment_reply(data: dict[str, Any], lang: str) -> tuple[str, str]:
    kind = "comment" if data.get("kind") == "comment" else "post"
    title = t(lang, f"comment_reply.{kind}.title", author=data.get("author_name", "?"))
    body = t(
        lang,
        "comment_reply.body",
        post=excerpt(data.get("post_title"), 60),
        excerpt=data.get("excerpt", ""),
    )
    return title, body


def _post_liked(data: dict[str, Any], lang: str) -> tuple[str, str]:
    count = int(data.get("count") or 1)
    key = "post_liked.title.one" if count == 1 else "post_liked.title.many"
    return t(lang, key, count=count), t(lang, "post_liked.body", post=data.get("post_title", ""))


def _content_hidden(data: dict[str, Any], lang: str) -> tuple[str, str]:
    kind = data.get("target_type") if data.get("target_type") in ("comment", "message") else "post"
    lines = [t(lang, "content_hidden.body", excerpt=excerpt(data.get("excerpt"), 80))]
    if data.get("reason"):
        lines.append(t(lang, "content_hidden.reason", reason=data["reason"]))
    return t(lang, f"content_hidden.{kind}.title"), "\n".join(lines)


def _price_alert(data: dict[str, Any], lang: str) -> tuple[str, str]:
    instrument = data.get("instrument") or {}
    digits = instrument.get("price_precision")
    digits = 2 if digits is None else int(digits)
    condition = data.get("condition", "above")
    value = data.get("value")
    is_pct = condition == "change_pct"
    shown_value = num(value, 2) if is_pct else num(value, digits)
    window = data.get("window_minutes")
    title = t(
        lang,
        "price_alert.title",
        symbol=instrument.get("symbol", "?"),
        condition=t(
            lang,
            f"cond.{condition}",
            value=shown_value,
            change=_signed(data.get("change_pct")),
            window=window,
        ),
    )
    bar = str(data.get("bar_time", ""))[:16].replace("T", " ")
    lines = [
        t(lang, "price_alert.price", price=num(data.get("price"), digits), bar=bar),
        t(
            lang,
            f"rule.{condition}",
            value=shown_value,
            window=window,
            previous=num(data.get("previous_close"), digits),
            reference=num(data.get("reference_close"), digits),
        ),
    ]
    if data.get("note"):
        lines.append(t(lang, "price_alert.note", note=data["note"]))
    if data.get("deactivated"):
        lines.append(t(lang, "price_alert.once"))
    return title, "\n".join(lines)


def _ai_setup(data: dict[str, Any], lang: str) -> tuple[str, str]:
    """An AI setup state change (B11): prices at the instrument's precision, the user's size on
    ARMED, the result of their take when it ends."""
    instrument = data.get("instrument") or {}
    digits = instrument.get("price_precision")
    digits = 2 if digits is None else int(digits)
    state = str(data.get("state", "ARMED"))
    side = t(lang, f"side.{data.get('direction', 'buy')}")
    symbol = instrument.get("symbol", "?")
    title = t(
        lang,
        f"ai_setup.{state}.title",
        side=side,
        symbol=symbol,
        entry=num(data.get("entry"), digits),
        r=_signed(data.get("realized_r")),
    )
    lines = []
    if state in ("ARMED", "ACTIVE"):
        lines.append(
            t(
                lang,
                "ai_setup.prices",
                entry=num(data.get("entry"), digits),
                sl=num(data.get("sl"), digits),
                tp=num(data.get("tp"), digits),
            )
        )
    if state == "ARMED":
        probability = data.get("probability")
        lines.append(
            t(
                lang,
                "ai_setup.scores",
                grade=data.get("grade") or "-",
                probability=num(probability * 100 if probability is not None else None, 0),
                r_multiple=num(data.get("r_multiple"), 1),
            )
        )
        if data.get("valid_until"):
            when = str(data["valid_until"])[11:16]
            lines.append(t(lang, "ai_setup.valid_until", time=when))
        size = data.get("size") or {}
        if "error" in size:
            lines.append(t(lang, "ai_setup.size_error"))
        elif size.get("feasible"):
            lines.append(
                t(
                    lang,
                    "ai_setup.size",
                    lots=num(size.get("lots"), 2),
                    risk=num(size.get("risk_amount"), 2),
                    currency=size.get("currency", ""),
                )
            )
        elif size:
            lines.append(t(lang, "ai_setup.size_infeasible"))
        for warning in (size.get("warnings") or [])[:2]:
            lines.append(t(lang, "ai_setup.warning", warning=warning))
        if data.get("explanation"):
            lines.append(str(data["explanation"]))
    if data.get("reason") and state != "ARMED":
        lines.append(t(lang, "ai_setup.reason", reason=data["reason"]))
    if data.get("pnl") is not None:
        lines.append(
            t(lang, "ai_setup.pnl", pnl=_signed(data["pnl"]), r=_signed(data.get("realized_r")))
        )
    if data.get("late"):
        lines.append(t(lang, "ai_setup.late"))
    return title, "\n".join(lines)


SOCIAL_RENDERERS = {
    "new_post": _new_post,
    "comment_reply": _comment_reply,
    "post_liked": _post_liked,
    "content_hidden": _content_hidden,
    "price_alert": _price_alert,
    "ai_setup": _ai_setup,
}


def _day(value: Any) -> str:
    return str(value or "")[:10]


def _subscription(event: str, data: dict[str, Any], lang: str) -> tuple[str, str]:
    f = {
        "expert": data.get("expert_name", "?"),
        "subscriber": data.get("subscriber_name", "?"),
        "plan": data.get("plan_name", ""),
        "price": num(data.get("price"), 2),
        "currency": data.get("currency", ""),
        "interval": t(lang, f"interval.{data.get('interval', 'month')}"),
        "date": _day(data.get("period_end")),
        "invoice": data.get("invoice_number", ""),
        "amount": num(data.get("amount"), 2),
        "reason": data.get("reason", ""),
        "grace": str(data.get("grace_end") or "")[:16].replace("T", " "),
        "days": data.get("trial_days", 0),
    }
    if event == "subscription_started":
        body = t(
            lang,
            "subscription_started.trial" if data.get("trial") else "subscription_started.paid",
            **f,
        )
    elif event == "subscription_renewed":
        body = t(lang, "subscription_renewed.body", **f)
    elif event == "subscription_payment_failed":
        body = t(lang, "subscription_payment_failed.body", **f)
    elif event == "subscription_canceled":
        reason = str(data.get("reason") or "period_end").split(":", 1)[0]
        body = t(lang, f"subscription_canceled.{reason}", **f)
    else:  # new_subscriber
        body = t(
            lang, "new_subscriber.trial" if data.get("trial_days") else "new_subscriber.paid", **f
        )
    return t(lang, f"{event}.title", **f), body


def _chat(data: dict[str, Any], lang: str) -> tuple[str, str]:
    count = int(data.get("count") or 1)
    key = "chat_message.title.one" if count == 1 else "chat_message.title.many"
    return t(lang, key, sender=data.get("sender_name", "?"), count=count), data.get("excerpt", "")


SUBSCRIPTION_EVENTS = (
    "subscription_started",
    "subscription_renewed",
    "subscription_payment_failed",
    "subscription_canceled",
    "new_subscriber",
)


def inbox(event: str, data: dict[str, Any], lang: str) -> tuple[str, str]:
    """Plain-text title and body (the inbox, and the base of every channel)."""
    if event == "signal":
        return _signal(data, lang)
    if event in ("backtest_completed", "backtest_failed"):
        return _backtest(event, data, lang)
    if event == "security":
        return _security(data, lang)
    if event in SOCIAL_RENDERERS:
        return SOCIAL_RENDERERS[event](data, lang)
    if event in SUBSCRIPTION_EVENTS:
        return _subscription(event, data, lang)
    if event == "chat_message":
        return _chat(data, lang)
    if data.get("test"):
        channel = CHANNEL_NAMES.get(lang, CHANNEL_NAMES["en"]).get(data.get("channel"), "")
        return t(lang, "test.title"), t(lang, "test.body", channel=channel)
    return str(data.get("title") or "")[:200], str(data.get("body") or "")


# --- channels --------------------------------------------------------------------------------


def telegram(title: str, body: str) -> str:
    """HTML parse mode: title in bold, everything escaped."""
    return f"<b>{html.escape(title)}</b>\n{html.escape(body)}"


def email(title: str, body: str, lang: str) -> tuple[str, str, str]:
    """(subject, plain text, HTML). Arabic is laid out right-to-left."""
    footer = t(lang, "email.footer")
    text = f"{body}\n\n--\n{footer}\n"
    direction = "rtl" if lang == "ar" else "ltr"
    align = "right" if lang == "ar" else "left"
    paragraphs = "".join(
        f'<p style="margin:0 0 8px">{html.escape(line) or "&nbsp;"}</p>'
        for line in body.split("\n")
    )
    page = (
        f'<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title></head>"
        f'<body dir="{direction}" style="font-family:Tahoma,Arial,sans-serif;'
        f'text-align:{align};color:#1f2933">'
        f'<h2 style="margin:0 0 12px">{html.escape(title)}</h2>{paragraphs}'
        f'<hr><p style="color:#7b8794;font-size:12px">{html.escape(footer)}</p>'
        "</body></html>"
    )
    return title, text, page


def deep_link(event: str, data: dict[str, Any], notification_id: str) -> dict[str, str]:
    """FCM ``data`` (strings only): where the app opens."""
    out = {"notification_id": notification_id, "type": event}
    if event == "signal":
        out.update(screen="signal", signal_id=str((data.get("signal") or {}).get("id", "")))
    elif event in ("backtest_completed", "backtest_failed"):
        out.update(screen="backtest", backtest_id=str(data.get("backtest_id", "")))
    elif event == "security":
        out.update(screen="security")
    elif event in ("new_post", "post_liked", "comment_reply", "content_hidden"):
        out.update(screen="post", post_id=str(data.get("post_id", "")))
        if data.get("comment_id"):
            out["comment_id"] = str(data["comment_id"])
    elif event == "chat_message":
        out.update(screen="chat", conversation_id=str(data.get("conversation_id", "")))
    elif event == "new_subscriber":
        out.update(screen="earnings", subscription_id=str(data.get("subscription_id", "")))
    elif event in SUBSCRIPTION_EVENTS:
        out.update(screen="subscription", subscription_id=str(data.get("subscription_id", "")))
    elif event == "ai_setup":
        out.update(
            screen="ai_setup",
            setup_id=str(data.get("setup_id", "")),
            state=str(data.get("state", "")),
            instrument_id=str((data.get("instrument") or {}).get("id", "")),
        )
    elif event == "price_alert":
        out.update(
            screen="price_alert",
            alert_id=str(data.get("alert_id", "")),
            instrument_id=str((data.get("instrument") or {}).get("id", "")),
        )
    else:
        out.update(screen="notifications")
    return out


def push(title: str, body: str) -> tuple[str, str]:
    """Short title/body: as many whole lines of the body as fit (never a cut number)."""
    parts: list[str] = []
    for line in (x for x in body.split("\n") if x):
        if len(" · ".join([*parts, line])) > PUSH_BODY_MAX:
            break
        parts.append(line)
    short = " · ".join(parts) or body[:PUSH_BODY_MAX]
    return title[:120], short


def digest(titles: list[str], lang: str, limit: int = 20) -> tuple[str, str]:
    lines = [t(lang, "digest.intro"), *(f"• {x}" for x in titles[:limit])]
    if len(titles) > limit:
        lines.append(t(lang, "digest.more", count=len(titles) - limit))
    return t(lang, "digest.title", count=len(titles)), "\n".join(lines)
