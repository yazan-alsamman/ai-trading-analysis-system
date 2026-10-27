"""A fake Gemini ``generateContent`` endpoint for development and CI (Y14, Y20). **Never in
production**: it is not in ``infra/deploy/docker-compose.prod.yml``, and the backend only talks
to it when ``CHART_VISION_BASE_URL`` points at it (empty by default, dev/CI only).

The backend's official ``google-genai`` client is pointed at it through
``HttpOptions(base_url=...)``, so the SDK, the request it builds and the parsing of the answer
are the real ones; only Google is replaced. It answers ``POST /{version}/models/{model}:
generateContent`` with what Gemini returns for structured output: one candidate whose text is
the JSON answer, ``finishReason`` and ``usageMetadata``.

- A one-colour image (every pixel the same) is "not a chart": ``is_chart`` false.
- Anything else is a chart: a fixed buy idea, in the requested language (read from the request
  text the backend sends: ``Requested language: ar``).
- ``POST /_fake/mode`` with ``{"mode": "ok" | "429" | "500" | "blocked"}`` changes the answer;
  ``GET /_fake/requests`` lists what was received (model, language, image type and size, whether
  the key came in the ``x-goog-api-key`` header: never the key or the image);
  ``POST /_fake/reset`` starts again.

Run it: ``uvicorn fake_gemini:app --app-dir tools/fake_gemini --port 8002`` (or the
``fake-gemini`` service of docker-compose.yml, profile ``fake-gemini``), then set
``CHART_VISION_BASE_URL=http://fake-gemini:8002`` and any non-empty ``GEMINI_API_KEY``.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from PIL import Image

app = FastAPI(title="fake Gemini (dev/CI only)", version="1.0.0")

MODES = ("ok", "429", "500", "blocked")
USAGE = {"promptTokenCount": 1290, "candidatesTokenCount": 310, "totalTokenCount": 1600}
TEXTS = {
    "en": {
        "summary": "Higher lows under a flat resistance; a close above it would confirm the "
        "breakout.",
        "reasoning": ["higher lows", "price above the moving average"],
        "pattern": "flat top with rising lows",
    },
    "ar": {
        "summary": "قيعان صاعدة تحت مقاومة أفقية؛ الإغلاق فوقها يؤكد الاختراق.",
        "reasoning": ["قيعان صاعدة", "السعر فوق المتوسط المتحرك"],
        "pattern": "قمة أفقية مع قيعان صاعدة",
    },
}


class _State:
    def __init__(self) -> None:
        self.mode = "ok"
        self.requests: list[dict[str, Any]] = []


STATE = _State()


def _answer(is_chart: bool, language: str) -> dict[str, Any]:
    if not is_chart:
        return {"is_chart": False, "summary": "", "reasoning": [], "warnings": []}
    text = TEXTS[language]
    return {
        "is_chart": True,
        "symbol_guess": "XAU/USD",
        "timeframe_guess": "15m",
        "trend": "up",
        "trend_strength": 0.7,
        "patterns": [
            {"name": "ascending triangle", "confidence": 0.62, "description": text["pattern"]}
        ],
        "support_levels": [2380.5, 2391.0],
        "resistance_levels": [2412.0],
        "indicators_seen": [{"name": "RSI(14)", "reading": "61"}],
        "idea": {
            "action": "buy",
            "confidence": 0.55,
            "entry": 2400.0,
            "stop_loss": 2390.0,
            "take_profit": 2420.0,
        },
        "summary": text["summary"],
        "reasoning": text["reasoning"],
        "warnings": [],
    }


def _b64(text: str) -> bytes:
    """The SDK sends url-safe base64 without padding; standard base64 is accepted too."""
    text = text.replace("-", "+").replace("_", "/")
    return base64.b64decode(text + "=" * (-len(text) % 4))


def _one_colour(data: bytes) -> bool:
    with Image.open(io.BytesIO(data)) as img:
        extrema = img.convert("RGB").getextrema()
    return all(low == high for low, high in extrema)


@app.post("/{version}/models/{call:path}")
async def generate_content(version: str, call: str, request: Request) -> JSONResponse:
    model, _, method = call.partition(":")
    if method != "generateContent":
        return JSONResponse({"error": {"code": 404, "message": "not faked"}}, status_code=404)
    body = await request.json()
    parts = body["contents"][0]["parts"]
    inline = next(p for p in parts if "inlineData" in p or "inline_data" in p)
    inline = inline.get("inlineData") or inline.get("inline_data")
    image = _b64(inline["data"])
    text = " ".join(p.get("text", "") for p in parts)
    match = re.search(r"Requested language: (ar|en)", text)
    language = match.group(1) if match else "en"
    is_chart = not _one_colour(image)
    STATE.requests.append(
        {
            "model": model,
            "language": language,
            "mime": inline.get("mimeType") or inline.get("mime_type"),
            "image_bytes": len(image),
            "key_in_header": bool(request.headers.get("x-goog-api-key")),
            "key_in_url": "key=" in str(request.url.query),
            "is_chart": is_chart,
        }
    )
    if STATE.mode in ("429", "500"):
        code = int(STATE.mode)
        status = "RESOURCE_EXHAUSTED" if code == 429 else "INTERNAL"
        return JSONResponse(
            {"error": {"code": code, "message": "fake", "status": status}}, status_code=code
        )
    if STATE.mode == "blocked":
        return JSONResponse({"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": USAGE})
    candidate = {
        "content": {
            "role": "model",
            "parts": [{"text": json.dumps(_answer(is_chart, language), ensure_ascii=False)}],
        },
        "finishReason": "STOP",
    }
    return JSONResponse({"candidates": [candidate], "usageMetadata": USAGE, "modelVersion": model})


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "fake": True, "mode": STATE.mode}


@app.post("/_fake/mode")
async def set_mode(request: Request) -> JSONResponse:
    mode = str((await request.json()).get("mode"))
    if mode not in MODES:
        return JSONResponse({"detail": f"unknown mode {mode}"}, status_code=400)
    STATE.mode = mode
    return JSONResponse({"mode": mode})


@app.post("/_fake/reset")
def reset() -> dict[str, str]:
    STATE.__init__()
    return {"mode": STATE.mode}


@app.get("/_fake/requests")
def requests() -> list[dict[str, Any]]:
    return STATE.requests
