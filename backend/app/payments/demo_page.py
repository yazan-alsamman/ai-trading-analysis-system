"""The demo provider's hosted payment page (HTML, served by the backend). No real money: the
page only accepts the test cards and never stores a card number."""

from __future__ import annotations

import html
from decimal import Decimal

TITLE = "Demo payment — no real money"

_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
background:#f4f6f8;color:#1f2933;
margin:0;padding:24px 16px}
main{max-width:440px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;
box-shadow:0 2px 12px rgba(0,0,0,.08)}
.banner{background:#fff4e5;border:1px solid #f5a623;color:#8a5300;border-radius:8px;
padding:10px 12px;font-weight:600;margin-bottom:16px}
h1{font-size:20px;margin:0 0 4px}.muted{color:#616e7c;font-size:14px}
.price{font-size:28px;font-weight:700;margin:12px 0}
label{display:block;font-size:13px;font-weight:600;margin:12px 0 4px}
input{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd2d9;
border-radius:8px;font-size:16px}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:18px;width:100%;padding:12px;border:0;border-radius:8px;background:#1f6feb;color:#fff;
font-size:16px;font-weight:600;cursor:pointer}
.error{background:#fde8e8;color:#9b1c1c;border-radius:8px;padding:10px 12px;margin-top:12px}
table{width:100%;font-size:13px;border-collapse:collapse;margin-top:16px}
td{padding:4px 0;border-top:1px solid #eef1f4}code{font-size:13px}
"""


def _page(body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{TITLE}</title><style>{_STYLE}</style></head><body><main>"
        f'<div class="banner">⚠ {TITLE}. Use a test card below.</div>{body}</main></body></html>'
    )


def _money(amount: Decimal, currency: str) -> str:
    return f"{amount:,.2f} {html.escape(currency)}"


def checkout_page(
    *,
    checkout_id: str,
    expert_name: str,
    plan_name: str,
    price: Decimal,
    currency: str,
    interval: str,
    trial_days: int,
    expires_at: str,
    error: str | None = None,
) -> str:
    charge = (
        f"Free for {trial_days} days, then {_money(price, currency)} / {interval}"
        if trial_days
        else f"{_money(price, currency)} / {interval}"
    )
    today = "0.00" if trial_days else f"{price:,.2f}"
    err = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return _page(
        f"<h1>{html.escape(plan_name)}</h1>"
        f'<div class="muted">Subscription to {html.escape(expert_name)}</div>'
        f'<div class="price">{html.escape(charge)}</div>'
        f'<div class="muted">Due today: {today} {html.escape(currency)}. '
        f"This page expires at {html.escape(expires_at)} UTC.</div>{err}"
        f'<form method="post" action="/api/v1/pay/demo/{html.escape(checkout_id)}/confirm">'
        '<label for="card">Card number</label>'
        '<input id="card" name="card_number" inputmode="numeric" autocomplete="off" '
        'placeholder="4242 4242 4242 4242" required>'
        '<div class="row"><div><label for="exp">Expiry (MM/YY)</label>'
        '<input id="exp" name="expiry" placeholder="12/30" required></div>'
        '<div><label for="cvc">CVC</label><input id="cvc" name="cvc" placeholder="123" '
        "required></div></div>"
        '<label for="name">Name on card</label><input id="name" name="name" required>'
        f'<button type="submit">Pay {today} {html.escape(currency)}</button></form>'
        "<table><tr><td><code>4242 4242 4242 4242</code></td><td>succeeds</td></tr>"
        "<tr><td><code>4000 0000 0000 0002</code></td><td>declined</td></tr>"
        "<tr><td><code>4000 0000 0000 9995</code></td><td>succeeds now, renewals fail</td></tr>"
        "</table>"
    )


def message_page(heading: str, text: str, ok: bool = True) -> str:
    color = "#0e7c3a" if ok else "#9b1c1c"
    return _page(
        f'<h1 style="color:{color}">{html.escape(heading)}</h1>'
        f'<p class="muted">{html.escape(text)}</p>'
    )
