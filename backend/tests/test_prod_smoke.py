"""Y20: the production smoke check (infra/smoke/prod_smoke.py, workflow prod-smoke.yml) is
read-only and quiet: GET only plus the login, the token masked and never printed, no response
body printed, ``warn`` for designed states (data degraded, a feature off) and ``fail`` only for a
real failure. Run against a local HTTP server standing in for the platform."""

import importlib.util
import json
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "smoke" / "prod_smoke.py"
WORKFLOW = ROOT / ".github" / "workflows" / "prod-smoke.yml"
TOKEN = "eyJ.smoke-token.secret"
EMAIL = "someone.private@example.com"  # in a body: must never be printed

spec = importlib.util.spec_from_file_location("prod_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
sys.modules["prod_smoke"] = smoke  # dataclasses look their module up
spec.loader.exec_module(smoke)

STATUS = {
    "ai_evaluate": {
        "enabled": True,
        "instruments": ["fxpro:XAU/USD"],
        "last_runs": [{"status": "ok", "at": "2027-01-14T10:00:20Z"}],
    },
    "ai_alerts": {"grades_enabled": False},
    "chart_analysis": {"enabled": False, "model": "gemini-3.6-flash",
                       "disabled_reason": "GEMINI_API_KEY is not set"},
    "feeds": {"ctrader": {"enabled": True, "state": "streaming", "connected": True,
                          "last_tick_at": "2027-01-14T10:01:00Z",
                          "link": {"token_expires_at": "2027-02-10T00:00:00Z"}}},
    "calendar": {"rows": 120000, "last_success": {"at": "2027-01-14T08:07:00Z"},
                 "last_error": None},
}  # fmt: skip


def routes(overrides: dict[str, tuple[int, Any]]) -> dict[str, tuple[int, Any]]:
    base = {
        "/api/v1/health": (200, {"status": "ok"}),
        "/api/v1/health/ready": (200, {"status": "ok"}),
        "/api/v1/health/data": (503, {"status": "degraded", "instruments": [
            {"instrument": "fxpro:XAU/USD", "status": "degraded"}]}),
        "/": (200, '<html><div id="root"></div></html>'),
        "/api/v1/market/instruments": (200, {"items": [{"is_active": True}], "total": 1}),
        "/api/v1/calendar/events": (200, {"items": [{"title": "CPI"}]}),
        "/api/v1/admin/system/status": (200, STATUS),
        "/api/v1/predictions": (200, {"items": [{"owner": EMAIL}], "total": 3}),
        "/api/v1/predictions/stats": (200, {"total": 3, "resolved": 2, "open": 1,
                                            "hit_rate": 0.5, "excluded_count": 0}),
        "/api/v1/admin/predictions/resolver": (200, {"last_run_at": "2027-01-14T10:00:00Z",
                                                     "last_status": "ok", "backlog": 0}),
        "/api/v1/analysis/chart-image/quota": (503, {"detail": {"code": "not_configured"}}),
        "/api/v1/me/recommendations": (200, [{"note": EMAIL}]),
    }  # fmt: skip
    return {**base, **overrides}


@pytest.fixture
def server(request) -> Iterator[tuple[str, list[tuple[str, str, dict]]]]:
    table = routes(getattr(request, "param", {}))
    seen: list[tuple[str, str, dict]] = []

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, method: str) -> None:
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else {}
            seen.append((method, self.path, {**dict(self.headers), "_body": body}))
            if method == "POST" and path == "/api/v1/auth/login":
                ok = body.get("password") == "right"
                status, payload = (200, {"access_token": TOKEN}) if ok else (401, {"detail": "x"})
            elif not self.headers.get("Authorization") and path not in (
                "/",
                "/api/v1/health",
                "/api/v1/health/ready",
                "/api/v1/health/data",
            ):
                status, payload = 401, {"detail": "Not authenticated"}
            else:
                status, payload = table.get(path, (404, {"detail": "Not Found"}))
            data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self._answer("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._answer("POST")

        def log_message(self, *args) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", seen
    httpd.shutdown()


def run(base: str, **env: str) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = smoke.main({"SMOKE_BASE_URL": base, **env}, lines.append)
    return code, lines


def test_signed_in_run_is_read_only_masked_and_passes_with_warnings(server) -> None:
    base, seen = server
    code, lines = run(base, SMOKE_EMAIL="smoke@example.com", SMOKE_PASSWORD="right")
    assert code == 0, lines
    methods = {(m, p.split("?")[0]) for m, p, _ in seen if m != "GET"}
    assert methods == {("POST", "/api/v1/auth/login")}  # the only write-shaped request
    assert not any("chart-image" in p and m == "POST" for m, p, _ in seen)
    output = "\n".join(lines)
    assert lines.count(f"::add-mask::{TOKEN}") == 1
    assert TOKEN not in output.replace(f"::add-mask::{TOKEN}", "")
    assert EMAIL not in output and "right" not in output.split("::add-mask::")[0]
    for expected in (
        "ok   ready: database, redis and migrations ok",
        "warn data: degraded (fxpro:XAU/USD degraded)",
        'ok   web: index.html with <div id="root">',
        "ok   ai evaluate: on (fxpro:XAU/USD), last run ok at 2027-01-14T10:00:20Z",
        "ok   ai grades: off",
        "warn chart analysis: off (gemini-3.6-flash): GEMINI_API_KEY is not set",
        "warn chart quota: 503 not_configured (the feature is off)",
        "ok   predictions: total 3, resolved 2, open 1, hit rate 50%, excluded 0",
        "ok   recommendations: 1 item(s) (limit 1)",
    ):
        assert expected in lines, (expected, lines)
    assert any(line.startswith("ok   ctrader feed: on, state streaming") for line in lines)
    assert lines[-1].endswith("0 fail")


def test_public_only_without_credentials(server) -> None:
    base, seen = server
    code, lines = run(base)
    assert code == 0
    assert all(m == "GET" for m, _, _ in seen)
    assert "ok   instruments: 401 without a login (auth enforced)" in lines
    assert "warn login: SMOKE_EMAIL / SMOKE_PASSWORD not set: public checks only" in lines


@pytest.mark.parametrize(
    ("server", "failed"),
    [
        ({"/api/v1/health/ready": (503, {"status": "degraded"})}, "fail ready: HTTP 503"),
        ({"/api/v1/predictions/stats": (500, {"detail": "boom"})}, "fail predictions: HTTP 500"),
        ({"/": (200, "<html>maintenance</html>")}, "fail web: HTTP 200: no web app"),
    ],
    indirect=["server"],
)
def test_real_failures_fail_the_job(server, failed) -> None:
    base, _ = server
    code, lines = run(base, SMOKE_EMAIL="smoke@example.com", SMOKE_PASSWORD="right")
    assert code == 1 and failed in lines, lines


def test_refused_login_fails_and_unreachable_host_fails(server) -> None:
    base, _ = server
    code, lines = run(base, SMOKE_EMAIL="smoke@example.com", SMOKE_PASSWORD="wrong")
    assert code == 1 and "fail login: refused (HTTP 401)" in lines
    code, lines = run("http://127.0.0.1:9")  # nothing listens
    assert code == 1 and lines[0].startswith("fail health: no answer")


def test_only_reads_are_allowed() -> None:
    s = smoke.Smoke("http://127.0.0.1:9")
    for method, path in (("DELETE", "/api/v1/x"), ("POST", "/api/v1/analysis/chart-image")):
        with pytest.raises(ValueError, match="read-only"):
            s.call(method, path)


def test_workflow_is_manual_only_and_has_no_ssh() -> None:
    flow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert set(flow[True]) == {"workflow_dispatch"}  # YAML reads the key "on" as True
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "ssh" not in text.lower().replace("no ssh", "")
    assert "secrets.VPS_HOST" in text and "secrets.SMOKE_PASSWORD" in text
