"""Y14: the vision module without any network. The result checks (clamping, wrong-side prices,
not a chart, the disclaimer), image validation and re-encoding (magic bytes, size, EXIF,
downscale, decompression bombs), and the Gemini call: the real SDK over a mocked HTTP
transport, and a fake client for blocked, empty, 429/5xx, network and timeout answers."""

import asyncio
import io
import json
import logging
import struct
import zlib
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import errors, types
from PIL import Image

from app.core.config import get_settings
from app.vision import gemini, images
from app.vision.images import ImageRejected, prepare, sniff
from app.vision.schemas import DISCLAIMERS, WARNINGS, ModelChartAnalysis, finalize

FAKE_KEY = "AIzaFAKE0000000000000000000000000000000"  # the log scan pattern; never a real key
MAX = 5_242_880


def png(width: int = 800, height: int = 500, color=(20, 120, 200)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, format="PNG")
    return out.getvalue()


def answer(**changes) -> ModelChartAnalysis:
    data = {
        "is_chart": True,
        "symbol_guess": "XAU/USD",
        "timeframe_guess": "15m",
        "trend": "up",
        "trend_strength": 0.7,
        "patterns": [{"name": "ascending triangle", "confidence": 0.62, "description": "flat top"}],
        "support_levels": [2380.5, 2391.0],
        "resistance_levels": [2412.0],
        "indicators_seen": [{"name": "RSI(14)", "reading": "about 61"}],
        "idea": {"action": "buy", "confidence": 0.55, "entry": 2400.0, "stop_loss": 2390.0,
                 "take_profit": 2420.0, "risk_reward": 9.9},
        "summary": "Higher lows under a flat resistance; a breakout above 2412 is likely.",
        "reasoning": ["higher lows", "RSI above 50"],
        "warnings": [],
    }  # fmt: skip
    data.update(changes)
    return ModelChartAnalysis.model_validate(data)


# --- the result ----------------------------------------------------------------------------------


def test_a_valid_result_and_the_disclaimer_in_both_languages() -> None:
    for language in ("ar", "en"):
        result = finalize(answer(), language)
        assert result.is_chart and result.trend == "up" and result.trend_strength == 0.7
        assert result.idea.entry == 2400.0 and result.idea.stop_loss == 2390.0
        assert result.idea.risk_reward == 2.0  # computed by code (20 / 10), not the model's 9.9
        assert result.support_levels == [2380.5, 2391.0]
        assert result.disclaimer == DISCLAIMERS[language]
    assert "not financial advice" in DISCLAIMERS["en"] and "ليس نصيحة مالية" in DISCLAIMERS["ar"]


def test_not_a_chart_empties_everything() -> None:
    result = finalize(answer(is_chart=False), "en")
    assert result.is_chart is False and result.idea is None and result.patterns == []
    assert result.summary == "" and result.support_levels == []
    assert result.disclaimer == DISCLAIMERS["en"]


def test_confidences_are_clamped() -> None:
    raw = answer(
        trend_strength=1.7,
        patterns=[{"name": "flag", "confidence": -0.2, "description": "d"}],
        idea={"action": "wait", "confidence": 3.0},
    )
    result = finalize(raw, "en")
    assert result.trend_strength == 1.0 and result.patterns[0].confidence == 0.0
    assert result.idea.confidence == 1.0 and result.idea.risk_reward is None


@pytest.mark.parametrize(
    ("idea", "kept"),
    [
        ({"action": "buy", "entry": 2400, "stop_loss": 2410, "take_profit": 2420}, False),
        ({"action": "buy", "entry": 2400, "stop_loss": 2390, "take_profit": 2395}, False),
        ({"action": "sell", "entry": 2400, "stop_loss": 2410, "take_profit": 2380}, True),
        ({"action": "sell", "entry": 2400, "stop_loss": 2390, "take_profit": 2380}, False),
        ({"action": "buy", "entry": 2400, "stop_loss": 2390}, True),  # partial but consistent
        (
            {"action": "buy", "entry": -5, "stop_loss": 2390, "take_profit": 2420},
            True,
        ),  # -5 dropped
    ],
)
def test_idea_prices_on_the_wrong_side_are_dropped(idea: dict, kept: bool) -> None:
    result = finalize(answer(idea={"confidence": 0.5, **idea}), "ar")
    assert result.idea.action == idea["action"]  # the idea itself is kept
    if kept:
        assert WARNINGS["ar"]["prices_dropped"] not in result.warnings
    else:
        assert (result.idea.entry, result.idea.stop_loss, result.idea.take_profit) == (
            None, None, None
        )  # fmt: skip
        assert result.idea.risk_reward is None
        assert result.warnings[-1] == WARNINGS["ar"]["prices_dropped"]
        assert result.summary  # the rest of the result is kept
    sell = finalize(answer(idea={"confidence": 0.5, **idea}), "en")
    if idea == {"action": "sell", "entry": 2400, "stop_loss": 2410, "take_profit": 2380}:
        assert sell.idea.risk_reward == 2.0


# --- images --------------------------------------------------------------------------------------


def test_type_from_magic_bytes() -> None:
    assert sniff(png()) == "image/png"
    jpeg = io.BytesIO()
    Image.new("RGB", (300, 300)).save(jpeg, format="JPEG")
    assert sniff(jpeg.getvalue()) == "image/jpeg"
    webp = io.BytesIO()
    Image.new("RGB", (300, 300)).save(webp, format="WEBP")
    assert sniff(webp.getvalue()) == "image/webp"
    assert sniff(b"GIF89a....") is None and sniff(b"<html>") is None
    with pytest.raises(ImageRejected) as exc:
        prepare(b"GIF89a" + b"\0" * 300, MAX)
    assert (exc.value.status, exc.value.code) == (415, "unsupported_image")


def test_size_and_dimension_limits() -> None:
    with pytest.raises(ImageRejected) as exc:
        prepare(png(), 1000)
    assert (exc.value.status, exc.value.code) == (413, "image_too_large")
    with pytest.raises(ImageRejected) as exc:
        prepare(png(150, 600), MAX)
    assert (exc.value.status, exc.value.code) == (422, "image_too_small")
    with pytest.raises(ImageRejected) as exc:
        prepare(b"\x89PNG\r\n\x1a\n" + b"garbage" * 50, MAX)
    assert (exc.value.status, exc.value.code) == (422, "invalid_image")


def test_downscale_and_exif_strip() -> None:
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90
    raw = io.BytesIO()
    Image.new("RGB", (3000, 1600), (200, 30, 30)).save(raw, format="JPEG", exif=exif.tobytes())
    data = raw.getvalue()
    assert b"SecretCam" in data
    prepared = prepare(data, MAX)
    assert (prepared.original_mime, prepared.mime) == ("image/jpeg", "image/png")
    assert (prepared.width, prepared.height) == (3000, 1600)
    sent = Image.open(io.BytesIO(prepared.data))
    assert max(sent.size) == 1568 and sent.size == (prepared.sent_width, prepared.sent_height)
    assert sent.size[0] < sent.size[1]  # the EXIF orientation was applied, then dropped
    assert sent.mode == "RGB" and not sent.getexif() and "exif" not in sent.info
    assert b"SecretCam" not in prepared.data
    assert len(prepared.sha256) == 64


def _png_header_only(width: int, height: int) -> bytes:
    """A PNG that claims ``width x height`` (a decompression bomb: tiny file, huge image)."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\0" * 64)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def test_decompression_bomb_is_refused_before_decoding() -> None:
    bomb = _png_header_only(30_000, 30_000)  # 900 Mpx in a few dozen bytes
    assert len(bomb) < 200
    with pytest.raises(ImageRejected) as exc:
        prepare(bomb, MAX)
    assert (exc.value.status, exc.value.code) == (422, "image_too_many_pixels")
    assert Image.MAX_IMAGE_PIXELS == images.MAX_PIXELS  # Pillow's own guard too


# --- the Gemini call -----------------------------------------------------------------------------


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "chart_analysis_enabled", True)
    monkeypatch.setattr(gemini, "BACKOFF_SECONDS", (0.0, 0.0))
    return settings


def response(parsed=None, *, finish="STOP", blocked=None, usage=(1290, 310, 1600)):
    return SimpleNamespace(
        parsed=parsed,
        prompt_feedback=SimpleNamespace(block_reason=blocked) if blocked else None,
        candidates=[SimpleNamespace(finish_reason=getattr(types.FinishReason, finish))],
        usage_metadata=SimpleNamespace(
            prompt_token_count=usage[0], candidates_token_count=usage[1], total_token_count=usage[2]
        ),
    )


class FakeClient:
    """``client.aio.models.generate_content`` answering from a list (exceptions are raised)."""

    def __init__(self, *answers, delay: float = 0.0) -> None:
        self.answers, self.calls, self.delay = list(answers), [], delay
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        item = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(item, BaseException):
            raise item
        return item


IMAGE = None


def image():
    global IMAGE
    IMAGE = IMAGE or prepare(png(), MAX)
    return IMAGE


async def test_real_sdk_request_over_a_mocked_transport(enabled, caplog) -> None:
    """The official SDK end to end, with the HTTP layer mocked: image first, then the text;
    JSON with the response schema, temperature 0.2 and the versioned prompt; the key only in
    a header; ``response.parsed`` validated; usage and latency logged, never the image."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"] = str(request.url), request.headers
        seen["body"] = json.loads(request.content)
        text = answer().model_dump_json()
        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": text}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 1290, "candidatesTokenCount": 310,
                              "totalTokenCount": 1600},
        })  # fmt: skip

    client = genai.Client(
        api_key=FAKE_KEY,
        http_options=types.HttpOptions(
            httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        ),
    )
    caplog.set_level(logging.INFO, logger="app.vision.gemini")
    result = await gemini.analyse(image(), "en", "XAU/USD", "15m", client=client)
    assert result.analysis.trend == "up" and result.model == "gemini-3.6-flash"
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (1290, 310, 1600)
    assert seen["url"].endswith("/models/gemini-3.6-flash:generateContent")
    assert FAKE_KEY not in seen["url"] and seen["headers"]["x-goog-api-key"] == FAKE_KEY
    body = seen["body"]
    parts = body["contents"][0]["parts"]
    assert list(parts[0]) == ["inlineData"] and parts[0]["inlineData"]["mime_type"] == "image/png"
    assert "Requested language: en" in parts[1]["text"] and "symbol=XAU/USD" in parts[1]["text"]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json" and config["temperature"] == 0.2
    assert "is_chart" in json.dumps(config["responseSchema"])
    assert body["systemInstruction"]["parts"][0]["text"] == gemini.prompt()
    log = caplog.text
    assert "model=gemini-3.6-flash is_chart=True tokens_in=1290 tokens_out=310 total=1600" in log
    assert FAKE_KEY not in log and parts[0]["inlineData"]["data"][:40] not in log


def test_prompt_is_versioned() -> None:
    text = gemini.prompt()
    assert gemini.PROMPT_VERSION == "chart_v1"
    for rule in ("is_chart", "Never invent a price", "wait", "guaranteed", "Arabic (ar)"):
        assert rule in text


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (response(blocked=types.BlockedReason.SAFETY), "blocked"),
        (response(answer(), finish="SAFETY"), "blocked"),
        (response(None), "empty_answer"),
        (response({"is_chart": "maybe"}), "invalid_answer"),
        (errors.ClientError(400, {"error": {"code": 400, "message": "bad image"}}),
         "could_not_analyse"),
    ],
)  # fmt: skip
async def test_refusals_become_422(enabled, reply, code) -> None:
    with pytest.raises(gemini.VisionRefused) as exc:
        await gemini.analyse(image(), "ar", client=FakeClient(reply))
    assert (exc.value.status, exc.value.code) == (422, code)


async def test_429_and_5xx_retried_twice_then_503(enabled) -> None:
    busy = errors.ClientError(429, {"error": {"code": 429, "message": "quota"}})
    client = FakeClient(busy)
    with pytest.raises(gemini.VisionUnavailable) as exc:
        await gemini.analyse(image(), "en", client=client)
    assert (exc.value.status, exc.value.code, exc.value.retry_after) == (503, "model_busy", 30)
    assert len(client.calls) == 3  # one try and two retries

    down = errors.ServerError(500, {"error": {"code": 500, "message": "internal"}})
    recovered = FakeClient(down, down, response(answer()))
    result = await gemini.analyse(image(), "en", client=recovered)
    assert result.attempts == 3 and result.analysis.is_chart

    thinking = response(answer())
    thinking.usage_metadata.thoughts_token_count = 500  # billed as output
    result = await gemini.analyse(image(), "en", client=FakeClient(thinking))
    assert (result.input_tokens, result.output_tokens) == (1290, 310 + 500)

    flaky = FakeClient(httpx.ConnectError("reset"))
    with pytest.raises(gemini.VisionUnavailable):
        await gemini.analyse(image(), "en", client=flaky)
    assert len(flaky.calls) == 3

    refused = FakeClient(errors.ClientError(403, {"error": {"code": 403, "message": "key"}}))
    with pytest.raises(gemini.VisionUnavailable) as exc:
        await gemini.analyse(image(), "en", client=refused)
    assert exc.value.code == "not_configured" and len(refused.calls) == 1

    weird = FakeClient(RuntimeError("sdk bug"))
    with pytest.raises(gemini.VisionUnavailable):  # never a 500
        await gemini.analyse(image(), "en", client=weird)


async def test_timeout_becomes_503(enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(enabled, "chart_vision_timeout_seconds", 0.2)
    with pytest.raises(gemini.VisionUnavailable) as exc:
        await gemini.analyse(image(), "en", client=FakeClient(response(answer()), delay=2))
    assert (exc.value.status, exc.value.code) == (503, "timeout")


def test_missing_key_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "")
    assert gemini.configured() == (False, "GEMINI_API_KEY is not set")
    with pytest.raises(gemini.VisionNotConfigured) as exc:
        gemini.get_client()
    assert exc.value.status == 503
    monkeypatch.setattr(settings, "gemini_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "chart_analysis_enabled", False)
    assert gemini.configured() == (False, "CHART_ANALYSIS_ENABLED=false")
    monkeypatch.setattr(settings, "chart_analysis_enabled", True)
    assert gemini.configured() == (True, None)
    assert gemini.get_client() is gemini.get_client()  # one client per process
