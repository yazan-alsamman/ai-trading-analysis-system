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


def inbox(event: str, data: dict[str, Any], lang: str) -> tuple[str, str]:
    """Plain-text title and body (the inbox, and the base of every channel)."""
    if event == "signal":
        return _signal(data, lang)
    if event in ("backtest_completed", "backtest_failed"):
        return _backtest(event, data, lang)
    if event == "security":
        return _security(data, lang)
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
