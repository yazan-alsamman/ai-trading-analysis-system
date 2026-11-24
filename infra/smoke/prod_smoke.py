"""Read-only smoke check of the live server (Y20), run by the ``Prod smoke`` workflow
(``.github/workflows/prod-smoke.yml``) after each deploy and on demo day. docs/deployment.md
explains it.

    SMOKE_BASE_URL=http://<host>:8080 [SMOKE_EMAIL=... SMOKE_PASSWORD=...] python prod_smoke.py

Rules (the reason it may run against production at any time):

- HTTP only, from outside, to the public port: no SSH, nothing on the server is touched;
- GET only; the one POST is the login (with credentials). Never DELETE, never the chart-image
  POST (it costs Gemini quota): :meth:`Smoke.call` refuses anything else;
- the token is masked in the GitHub log (``::add-mask::``) and never printed; response bodies
  are never printed, only counts, statuses and feature flags;
- one line per check: ``ok``, ``warn`` (worth a look, the job still passes: data degraded, a
  feature switched off, a non-admin smoke account) or ``fail`` (the job fails: a 5xx other than a
  designed 503, the API or its readiness down, the web app missing, the login refused).

Standard library only: the runner needs nothing installed.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

LOGIN = "/api/v1/auth/login"
TIMEOUT = 20
LEVELS = ("ok", "warn", "fail")


@dataclass
class Reply:
    status: int  # 0: no answer (connection refused, timeout)
    body: bytes = b""
    error: str = ""

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except ValueError:
            return None

    def code(self) -> str | None:
        """The ``detail.code`` of a structured error (e.g. ``not_configured``)."""
        body = self.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        return detail.get("code") if isinstance(detail, dict) else None


@dataclass
class Smoke:
    base: str
    out: Callable[[str], None] = print
    token: str | None = None
    lines: list[tuple[str, str, str]] = field(default_factory=list)

    def call(self, method: str, path: str, body: dict | None = None) -> Reply:
        if method != "GET" and not (method == "POST" and path == LOGIN):
            raise ValueError(f"read-only: {method} {path} is not allowed")
        headers = {"Accept": "application/json", "User-Agent": "prod-smoke"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = self.base + path
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as res:
                return Reply(res.status, res.read())
        except urllib.error.HTTPError as exc:
            return Reply(exc.code, exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Reply(0, error=type(exc).__name__)

    def line(self, level: str, name: str, detail: str) -> None:
        assert level in LEVELS
        self.lines.append((level, name, detail))
        self.out(f"{level:<4} {name}: {detail}")

    def status_line(self, name: str, reply: Reply, detail: str = "") -> bool:
        """``fail`` for no answer or a 5xx; True when the reply is a 200."""
        if reply.status == 0:
            self.line("fail", name, f"no answer ({reply.error})")
        elif reply.status >= 500:
            self.line("fail", name, f"HTTP {reply.status}")
        elif reply.status != 200:
            self.line("warn", name, f"HTTP {reply.status} {detail}".rstrip())
        return reply.status == 200

    @property
    def failed(self) -> bool:
        return any(level == "fail" for level, _, _ in self.lines)


def _on(value: Any) -> str:
    return "on" if value else "off"


def _days_left(when: str | None, now: datetime) -> float | None:
    if not when:
        return None
    at = datetime.fromisoformat(str(when))  # 3.11+ reads "Z"
    return (at - now).total_seconds() / 86400


# --- the checks ----------------------------------------------------------------------------------


def public(s: Smoke) -> None:
    reply = s.call("GET", "/api/v1/health")
    if s.status_line("health", reply):
        s.line("ok", "health", "200")
    reply = s.call("GET", "/api/v1/health/ready")
    body = reply.json() or {}
    if reply.status == 200 and isinstance(body, dict) and body.get("status") == "ok":
        s.line("ok", "ready", "database, redis and migrations ok")
    else:
        s.line("fail", "ready", f"HTTP {reply.status} {reply.error}".rstrip())
    reply = s.call("GET", "/api/v1/health/data")
    body = reply.json() or {}
    if reply.status in (200, 503) and isinstance(body, dict):
        states = [f"{i.get('instrument')} {i.get('status')}" for i in body.get("instruments", [])]
        level = "ok" if reply.status == 200 else "warn"  # 503 = degraded or no data, by design
        s.line(level, "data", f"{body.get('status', '?')} ({', '.join(states) or 'none'})")
    else:
        s.status_line("data", reply)
    reply = s.call("GET", "/")
    if reply.status == 200 and b'<div id="root"' in reply.body:
        s.line("ok", "web", 'index.html with <div id="root">')
    else:
        s.line("fail", "web", f"HTTP {reply.status}: no web app")
    for name, path in (("instruments", "/api/v1/market/instruments"), ("calendar", _calendar())):
        reply = s.call("GET", path)
        if reply.status == 401:
            s.line("ok", name, "401 without a login (auth enforced)")
        else:
            s.status_line(name, reply, "(expected 401 without a login)")


def _calendar(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    query = urllib.parse.urlencode(
        {"start": (now - timedelta(days=7)).isoformat(), "end": now.isoformat()}
    )
    return f"/api/v1/calendar/events?{query}"


def login(s: Smoke, email: str, password: str, mask: Callable[[str], None]) -> bool:
    reply = s.call("POST", LOGIN, {"email": email, "password": password})
    token = (reply.json() or {}).get("access_token") if reply.status == 200 else None
    if not token:
        s.line("fail", "login", f"refused (HTTP {reply.status})")
        return False
    mask(token)
    s.token = token
    s.line("ok", "login", "200 (token masked)")
    return True


def signed_in(s: Smoke, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    reply = s.call("GET", "/api/v1/market/instruments?limit=100")
    if s.status_line("instruments", reply):
        body = reply.json()
        active = sum(1 for i in body["items"] if i.get("is_active"))
        s.line("ok", "instruments", f"{body['total']} ({active} active in the first page)")
    reply = s.call("GET", _calendar(now))
    if s.status_line("calendar", reply):
        n = len((reply.json() or {}).get("items", []))
        s.line("ok" if n else "warn", "calendar", f"{n} events in the last 7 days")
    reply = s.call("GET", "/api/v1/admin/system/status")
    if reply.status == 403:
        s.line("warn", "flags", "the smoke account is not an admin: no system status")
    elif s.status_line("flags", reply):
        flags(s, reply.json(), now)
    for name, path, show in (
        ("ai setups", "/api/v1/predictions?source=ai&limit=1", _total),
        ("predictions", "/api/v1/predictions/stats", _stats),
        ("resolver", "/api/v1/admin/predictions/resolver", _resolver),
        ("chart quota", "/api/v1/analysis/chart-image/quota", _quota),
        ("recommendations", "/api/v1/me/recommendations?limit=1", _count),
    ):
        reply = s.call("GET", path)
        if reply.status == 503 and reply.code() == "not_configured":
            s.line("warn", name, "503 not_configured (the feature is off)")
        elif reply.status == 403 and name == "resolver":
            s.line("warn", name, "not an admin: skipped")
        elif s.status_line(name, reply):
            s.line("ok", name, show(reply.json()))


def _total(body: dict) -> str:
    return f"{body['total']} published"


def _stats(body: dict) -> str:
    rate = body.get("hit_rate")
    hit = "n/a" if rate is None else f"{rate:.0%}"
    return (
        f"total {body['total']}, resolved {body['resolved']}, open {body['open']}, "
        f"hit rate {hit}, excluded {body['excluded_count']}"
    )


def _resolver(body: dict) -> str:
    return (
        f"last run {body.get('last_run_at') or 'never'} ({body.get('last_status') or '-'}), "
        f"backlog {body.get('backlog')}"
    )


def _quota(body: dict) -> str:
    return f"limit {body['limit']}, used {body['used']}"


def _count(body: list) -> str:
    return f"{len(body)} item(s) (limit 1)"


def flags(s: Smoke, status: dict, now: datetime) -> None:
    """The feature flags of ``/admin/system/status`` (no personal data in it)."""
    ai = status.get("ai_evaluate") or {}
    runs = ai.get("last_runs") or []
    last = max(runs, key=lambda r: r.get("at") or "", default=None)
    run = f", last run {last['status']} at {last['at']}" if last else ", no run yet"
    s.line(
        "ok" if ai.get("enabled") else "warn",
        "ai evaluate",
        f"{_on(ai.get('enabled'))} ({', '.join(ai.get('instruments') or [])}){run}",
    )
    grades = (status.get("ai_alerts") or {}).get("grades_enabled")
    s.line("ok", "ai grades", _on(grades) if grades is not None else "not reported")
    chart = status.get("chart_analysis") or {}
    detail = f"{_on(chart.get('enabled'))} ({chart.get('model')})"
    if not chart.get("enabled") and chart.get("disabled_reason"):
        detail += f": {chart['disabled_reason']}"
    s.line("ok" if chart.get("enabled") else "warn", "chart analysis", detail)
    feed = ((status.get("feeds") or {}).get("ctrader")) or {}
    expires = (feed.get("link") or {}).get("token_expires_at")
    days = _days_left(expires, now)
    detail = (
        f"{_on(feed.get('enabled'))}, state {feed.get('state')}, "
        f"connected {_on(feed.get('connected'))}, last tick {feed.get('last_tick_at')}"
    )
    if days is not None:
        detail += f", token expires {str(expires)[:10]} ({days:.0f} days, refreshed under 7)"
    level = "ok" if feed.get("enabled") and feed.get("connected") else "warn"
    if days is not None and days < 3:
        level = "warn"
    s.line(level, "ctrader feed", detail)
    calendar = status.get("calendar") or {}
    ok_at = (calendar.get("last_success") or {}).get("at")
    error_at = (calendar.get("last_error") or {}).get("at")
    fresh = ok_at is not None and (error_at is None or str(ok_at) >= str(error_at))
    detail = f"{calendar.get('rows')} rows, last success {ok_at}"
    if error_at and not fresh:
        detail += f", last error {error_at}"
    s.line("ok" if fresh else "warn", "calendar refresh", detail)


def main(environ: dict[str, str] | None = None, out: Callable[[str], None] = print) -> int:
    env = os.environ if environ is None else environ
    base = env.get("SMOKE_BASE_URL") or (
        f"http://{env['VPS_HOST']}:8080" if env.get("VPS_HOST") else ""
    )
    if not base:
        out("fail config: neither SMOKE_BASE_URL nor VPS_HOST is set")
        return 1
    s = Smoke(base.rstrip("/"), out)
    public(s)
    email, password = env.get("SMOKE_EMAIL"), env.get("SMOKE_PASSWORD")
    if email and password:
        if login(s, email, password, lambda token: out(f"::add-mask::{token}")):
            signed_in(s)
    else:
        s.line("warn", "login", "SMOKE_EMAIL / SMOKE_PASSWORD not set: public checks only")
    counts = {level: sum(1 for x in s.lines if x[0] == level) for level in LEVELS}
    out(f"summary: {counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail")
    return 1 if s.failed else 0


if __name__ == "__main__":
    sys.exit(main())
