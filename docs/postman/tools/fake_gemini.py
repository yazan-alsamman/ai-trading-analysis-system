"""A stand-in for the Gemini API, so capture_examples.py records chart image analysis without a
key or a paid call. Start it, then start the backend with

    GEMINI_API_KEY=fake CHART_VISION_BASE_URL=http://localhost:8765

It answers ``generateContent`` with a fixed analysis of ``samples/chart_sample.png`` in the
requested language, and ``is_chart: false`` for an image of one colour
(``samples/not_a_chart.png``). It never sees a real key.

    python docs/postman/tools/fake_gemini.py [--port 8765]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

TEXTS = {
    "en": {
        "pattern": ("ascending channel", "Higher lows since 2381 and higher highs since 2390."),
        "rsi": "about 64, rising",
        "summary": "Price broke above the 2397 range high and is making higher highs. A "
        "pullback that holds above 2397 would keep the uptrend likely; a close back under it "
        "would weaken it.",
        "reasoning": ["Higher lows since 2381", "Break of the 2397 range high"],
        "warnings": ["No volume visible on the chart"],
    },
    "ar": {
        "pattern": ("قناة صاعدة", "قيعان صاعدة منذ 2381 وقمم صاعدة منذ 2390."),
        "rsi": "حوالي 64 وصاعد",
        "summary": "اخترق السعر قمة النطاق عند 2397 ويصنع قمماً أعلى. ارتداد يبقى فوق 2397 يجعل "
        "استمرار الصعود مرجّحاً، والإغلاق دونها يضعفه.",
        "reasoning": ["قيعان صاعدة منذ 2381", "اختراق قمة النطاق عند 2397"],
        "warnings": ["لا يظهر حجم التداول على الشارت"],
    },
}


def analysis(language: str, is_chart: bool) -> dict:
    if not is_chart:
        return {"is_chart": False}
    t = TEXTS[language]
    return {
        "is_chart": True,
        "symbol_guess": "XAU/USD",
        "timeframe_guess": "15m",
        "trend": "up",
        "trend_strength": 0.68,
        "patterns": [{"name": t["pattern"][0], "confidence": 0.6, "description": t["pattern"][1]}],
        "support_levels": [2381.0, 2397.0],
        "resistance_levels": [2408.0],
        "indicators_seen": [{"name": "RSI(14)", "reading": t["rsi"]}],
        "idea": {
            "action": "buy",
            "confidence": 0.55,
            "entry": 2406.0,
            "stop_loss": 2398.0,
            "take_profit": 2422.0,
            "risk_reward": 9.9,  # recomputed by the backend: 2.0
        },
        "summary": t["summary"],
        "reasoning": t["reasoning"],
        "warnings": t["warnings"],
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        parts = [p for c in body.get("contents", []) for p in c.get("parts", [])]
        text = " ".join(p.get("text", "") for p in parts)
        language = "ar" if "Requested language: ar" in text else "en"
        image = next((p["inlineData"] for p in parts if "inlineData" in p), None)
        is_chart = True
        if image is not None:
            data = image["data"] + "=" * (
                -len(image["data"]) % 4
            )  # the SDK sends url-safe, unpadded
            pixels = Image.open(io.BytesIO(base64.urlsafe_b64decode(data))).convert("RGB")
            is_chart = any(lo != hi for lo, hi in pixels.getextrema())
        answer = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": json.dumps(analysis(language, is_chart))}],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1612,
                "candidatesTokenCount": 412 if is_chart else 9,
                "thoughtsTokenCount": 238,
                "totalTokenCount": 2262 if is_chart else 1859,
            },
            "modelVersion": "gemini-3.6-flash",
        }
        data = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args: object) -> None:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    port = parser.parse_args().port
    print(f"fake Gemini on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
