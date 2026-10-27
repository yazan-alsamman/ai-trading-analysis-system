"""A fake ai-service for development and CI (B9). **Never in production**: it is not in
``infra/deploy/docker-compose.prod.yml`` and not under ``ai-service/`` (Fadi's).

It answers ``POST /v1/evaluate``, ``/v1/size`` and ``/v1/explain`` and ``GET /health`` with
the committed examples (docs/api/ai-service-examples) or deterministic answers, and can be
driven with ``POST /_fake/mode`` to return what a test needs:

- ``evaluate``: ``lifecycle`` (default: a DEVELOPING setup, then ARMED, ACTIVE and CLOSED on
  the next requests, with the full history in ``transitions``), ``rules_only`` (the same life
  cycle as Fadi's v1 answers it, contract 0.2.1: ``ok`` with ``versions.model`` null and
  ``probability``, ``ev_r``, ``ev_r_lower`` and ``grade`` null; ``/health`` reports no model
  either), ``same_at`` (DEVELOPING, then
  ARMED and ACTIVE with the same ``at``, then CLOSED), ``examples`` (the ok example),
  ``model_unavailable``, ``abstain`` (``ok`` with an abstention and no setup, as the v1 rules
  answer when nothing qualifies), ``backwards`` (the lifecycle, then the setup sent back as
  DEVELOPING), ``422``, ``503``, ``404``;
- ``size``: ``404`` (default: no ``/v1/size`` yet, as before Fadi's P6), ``ok`` (the example),
  ``503``;
- ``explain``: ``404`` (default, before P7), ``verified`` (the example), ``template``
  (verified false, template_used true), ``unverified`` (both false), ``503``.

Deterministic: the same evaluate body always gets the same response bytes (Fadi, point 16).
Request bodies may be gzip-compressed (``Content-Encoding: gzip``). ``GET /_fake/requests``
lists what was received (path, request id, body size), ``POST /_fake/reset`` starts again.

Run it: ``uvicorn fake_ai_service:app --app-dir tools/fake_ai_service --port 8001`` (or the
``fake-ai`` service of docker-compose.yml, profile ``fake-ai``), then point ``AI_SERVICE_URL``
at it.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# in the repository: docs/api/ai-service-examples; in the fake-ai container: FAKE_AI_EXAMPLES
EXAMPLES = (
    Path(os.environ["FAKE_AI_EXAMPLES"])
    if os.environ.get("FAKE_AI_EXAMPLES")
    else Path(__file__).resolve().parents[2] / "docs" / "api" / "ai-service-examples"
)
VERSIONS = {"strategy": "fake-1.0.0", "model": "fake-model-1", "features": "fake-f1"}
RULES_ONLY_VERSIONS = {**VERSIONS, "model": None}  # v1: the rules alone (contract 0.2.1)
MODEL_SCORES = ("probability", "ev_r", "ev_r_lower", "grade")
DEFAULT_MODES = {"evaluate": "lifecycle", "size": "404", "explain": "404"}

app = FastAPI(title="fake ai-service (dev/CI only)", version="0.2.1")


class _State:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.modes: dict[str, str] = dict(DEFAULT_MODES)
        self.requests: list[dict[str, Any]] = []
        self.answers: dict[str, bytes] = {}  # body hash -> response bytes (determinism)
        self.steps: list[str] = []  # distinct evaluate request ids, in order
        self.first: dict[str, Any] | None = None  # the lifecycle setup's first request


STATE = _State()


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


async def _body(request: Request) -> tuple[bytes, Any]:
    raw = await request.body()
    if request.headers.get("content-encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw, json.loads(raw) if raw else None


def _record(path: str, request: Request, raw: bytes) -> None:
    STATE.requests.append(
        {
            "path": path,
            "request_id": request.headers.get("x-request-id"),
            "bytes": len(raw),
            "gzip": request.headers.get("content-encoding") == "gzip",
        }
    )


def _status(mode: str) -> Response | None:
    if mode == "404":
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if mode == "503":
        return JSONResponse({"detail": "model loading"}, status_code=503)
    if mode == "422":
        detail = [
            {
                "loc": ["body", "bars"],
                "msg": "fake validation error",
                "type": "value_error",
            }
        ]
        return JSONResponse({"detail": detail}, status_code=422)
    return None


def _tick(value: float, tick: float) -> float:
    steps = (Decimal(str(value)) / Decimal(str(tick))).quantize(
        Decimal(1), rounding=ROUND_FLOOR
    )
    return float(steps * Decimal(str(tick)))


def _lifecycle(body: dict[str, Any], mode: str) -> dict[str, Any]:
    """One buy setup moving one state per new request: DEVELOPING, ARMED, ACTIVE, CLOSED."""
    if body["request_id"] not in STATE.steps:
        STATE.steps.append(body["request_id"])
    k = STATE.steps.index(body["request_id"])
    if STATE.first is None:
        STATE.first = body
    first = STATE.first
    tick = first["instrument_spec"]["tick_size"]
    close = first["bars"]["15m"][-1]["c"]
    entry = _tick(close, tick)
    born = first["bar_close_ts"]
    setup_id = f"fake-{first['instrument'].lower()}-{first['profile']}-{born}-buy"
    times = [s.split("-", 2)[2] for s in STATE.steps]  # the bar_close_ts of each step
    history = [
        ("DEVELOPING", "ARMED", 1, "trigger", None),
        ("ARMED", "ACTIVE", 2, "entry_filled", None),
        ("ACTIVE", "CLOSED", 3, "tp_hit", 2.0),
    ]
    if mode == "same_at":  # ARMED and ACTIVE together, on the second bar
        history = [
            ("DEVELOPING", "ARMED", 1, "trigger", None),
            ("ARMED", "ACTIVE", 1, "entry_filled", None),
            ("ACTIVE", "CLOSED", 2, "tp_hit", 2.0),
        ]
    done = [h for h in history if h[2] <= k]
    state = done[-1][1] if done else "DEVELOPING"
    if mode == "backwards" and k >= 2:
        state = "DEVELOPING"  # a contract error: the state goes back
        done = []
    priced = state in ("ARMED", "ACTIVE")
    setup = {
        "setup_id": setup_id,
        "state": state,
        "direction": "buy",
        "entry": entry if priced or state == "CLOSED" else None,
        "sl": _tick(entry - 5 * 100 * tick, tick)
        if priced or state == "CLOSED"
        else None,
        "tp": _tick(entry + 10 * 100 * tick, tick)
        if priced or state == "CLOSED"
        else None,
        "r_multiple": 2.0,
        "probability": 0.58,
        "ev_r": 0.74,
        "ev_r_lower": 0.31,
        "grade": None,
        "valid_until": None,
        "horizon_until": None,
        "created_at": born,
        "evidence": {"fake": True},
        "features": {"step": k},
    }
    if mode == "rules_only":  # no model: no scores
        setup.update(dict.fromkeys(MODEL_SCORES))
    transitions = [
        {
            "setup_id": setup_id,
            "from": frm,
            "to": to,
            "at": times[step],
            "reason": reason,
            "realized_r": realized,
        }
        for frm, to, step, reason, realized in done
    ]
    return {
        "request_id": body["request_id"],
        "status": "ok",
        "versions": _versions(),
        "new_setups": [setup],
        "transitions": transitions,
        "abstentions": [],
    }


def _versions() -> dict[str, Any]:
    return RULES_ONLY_VERSIONS if STATE.modes["evaluate"] == "rules_only" else VERSIONS


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "versions": _versions(), "fake": True}


@app.post("/v1/evaluate")
async def evaluate(request: Request) -> Response:
    raw, body = await _body(request)
    _record("/v1/evaluate", request, raw)
    mode = STATE.modes["evaluate"]
    if (answer := _status(mode)) is not None:
        return answer
    key = hashlib.sha256(raw).hexdigest()
    if key not in STATE.answers:
        if mode == "examples":
            out = {**example("evaluate-response-ok"), "request_id": body["request_id"]}
        elif mode == "abstain":
            out = {
                "request_id": body["request_id"],
                "status": "ok",
                "versions": RULES_ONLY_VERSIONS,
                "new_setups": [],
                "transitions": [],
                "abstentions": [{"reason": "no_setup", "detail": {"fake": True}}],
            }
        elif mode == "model_unavailable":
            out = {
                **example("evaluate-response-model-unavailable"),
                "request_id": body["request_id"],
            }
        else:
            out = _lifecycle(body, mode)
        STATE.answers[key] = json.dumps(out, sort_keys=True).encode()
    return Response(STATE.answers[key], media_type="application/json")


@app.post("/v1/size")
async def size(request: Request) -> Response:
    raw, _ = await _body(request)
    _record("/v1/size", request, raw)
    mode = STATE.modes["size"]
    if (answer := _status(mode)) is not None:
        return answer
    return JSONResponse(example("size-response"))


@app.post("/v1/explain")
async def explain(request: Request) -> Response:
    raw, body = await _body(request)
    _record("/v1/explain", request, raw)
    mode = STATE.modes["explain"]
    if (answer := _status(mode)) is not None:
        return answer
    text = (
        example("explain-response")["text"] if body["lang"] == "ar" else "A buy setup."
    )
    flags = {
        "verified": (True, False),
        "template": (False, True),
        "unverified": (False, False),
    }[mode]
    if mode == "template":
        text = f"Template: buy at {body['setup']['entry']}"
    return JSONResponse({"text": text, "verified": flags[0], "template_used": flags[1]})


@app.post("/_fake/mode")
async def set_mode(request: Request) -> dict[str, str]:
    changes = await request.json()
    for name, value in changes.items():
        if name not in DEFAULT_MODES:
            return JSONResponse({"detail": f"unknown endpoint {name}"}, status_code=400)
        STATE.modes[name] = str(value)
    return STATE.modes


@app.post("/_fake/reset")
def reset() -> dict[str, str]:
    STATE.reset()
    return STATE.modes


@app.get("/_fake/requests")
def requests() -> list[dict[str, Any]]:
    return STATE.requests
