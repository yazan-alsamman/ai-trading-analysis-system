"""Step 11 (Y14): chart image analysis through Nginx, with the backend's real ``google-genai``
client pointed at the fake Gemini (tools/fake_gemini, profile ``fake-gemini``; the e2e job sets
``GEMINI_API_KEY`` to a dummy and ``CHART_VISION_BASE_URL=http://fake-gemini:8002``). **CI never
calls Gemini.**

A chart in English and in Arabic (200), a one-colour image (422 ``not_a_chart``, counted), the
same image again (free: no model call, no quota), the daily quota (429 with ``Retry-After``),
another user's row (404 on GET and DELETE), and the feature switched off with one setting and the
backend recreated (503), as in the demo-day rollback (docs/demo-day.md).
"""

import math
import struct
import zlib

from tests_e2e.conftest import compose, fake, need, system_status, wait_for, wait_until_ready

WIDTH, HEIGHT = 400, 300
HINTS = {"symbol": "XAU/USD", "timeframe": "15m"}


def png(pixel) -> bytes:
    """A small RGB PNG, written by hand (the runner has no imaging library)."""
    rows = b"".join(
        b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(WIDTH)) for y in range(HEIGHT)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def chart(seed: int) -> bytes:
    """A price line on a white background, different for every seed."""
    line = [
        int(HEIGHT / 2 + 60 * math.sin(x / (20 + seed)) - x * 0.2 + seed * 7) for x in range(WIDTH)
    ]
    return png(lambda x, y: (20, 120, 60) if abs(y - line[x]) <= 1 else (255, 255, 255))


BLANK = png(lambda x, y: (240, 240, 240))  # one colour: not a chart


def test_chart_analysis(http, world, make_account):
    need(system_status(http, world)["chart_analysis"]["enabled"], "chart analysis (Y14)")
    user, other = make_account("chart"), make_account("analyst")  # "chart": a fresh trader
    fake("fake-gemini", 8002, "/_fake/reset", {})

    def post(image: bytes, language: str):
        return http.post(
            "/analysis/chart-image",
            files={"image": ("chart.png", image, "image/png")},
            data={"language": language, **HINTS},
            headers=user.h,
        )

    def used() -> int:
        res = http.get("/analysis/chart-image/quota", headers=user.h)
        assert res.status_code == 200, res.text
        return res.json()["used"]

    limit = http.get("/analysis/chart-image/quota", headers=user.h).json()["limit"]
    assert limit >= 4, limit  # trader: CHART_ANALYSIS_DAILY_LIMIT_TRADER (5)

    # a chart, in English and in Arabic
    res = post(chart(1), "en")
    assert res.status_code == 200, res.text
    en = res.json()
    assert (en["status"], en["language"], en["cached"]) == ("ok", "en", False)
    result = en["result"]
    assert result["is_chart"] and result["trend"] == "up"
    assert result["idea"]["risk_reward"] == 2.0  # computed by the backend: 20 / 10
    assert "not financial advice" in result["disclaimer"]
    assert en["usage"]["input_tokens"] == 1290 and en["image"]["sha256"]
    res = post(chart(1), "ar")
    assert res.status_code == 200, res.text
    ar = res.json()["result"]
    assert "ليس نصيحة مالية" in ar["disclaimer"] and "قيعان" in ar["summary"]

    # not a chart: refused, but counted (the model was asked)
    res = post(BLANK, "en")
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "not_a_chart" and detail["analysis_id"], detail
    assert used() == 3

    # the same image, language and hints again: the stored answer, free
    res = post(chart(1), "en")
    assert res.status_code == 200 and res.json()["cached"] is True, res.text
    assert res.json()["id"] == en["id"] and used() == 3

    # up to the daily quota, then 429 with Retry-After (no model call)
    for seed in range(2, 2 + limit - 3):
        assert post(chart(seed), "en").status_code == 200
    res = post(chart(99), "en")
    assert res.status_code == 429, res.text
    assert res.json()["detail"]["code"] == "quota_exceeded"
    assert 0 < int(res.headers["Retry-After"]) <= 86400
    calls = fake("fake-gemini", 8002, "/_fake/requests")
    assert len(calls) == limit  # the duplicate and the refused one never reached the model
    assert all(c["key_in_header"] and not c["key_in_url"] for c in calls), calls
    assert {c["language"] for c in calls} == {"ar", "en"}

    # history, and another user's row
    page = http.get("/analysis/chart-image", headers=user.h).json()
    assert page["total"] == limit and {i["status"] for i in page["items"]} == {"ok", "not_chart"}
    url = f"/analysis/chart-image/{en['id']}"
    assert http.get(url, headers=other.h).status_code == 404
    assert http.delete(url, headers=other.h).status_code == 404
    assert http.get(url, headers=user.h).status_code == 200
    assert http.delete(url, headers=user.h).status_code == 204
    assert http.get(url, headers=user.h).status_code == 404

    # switched off with one setting (the backend recreated): 503, the rest of the API works
    try:
        compose(
            "up", "-d", "--no-deps", "--wait", "backend", env={"CHART_ANALYSIS_ENABLED": "false"}
        )
        wait_until_ready(http)
        res = post(chart(100), "en")
        assert res.status_code == 503, res.text
        assert res.json()["detail"]["code"] == "not_configured"
        assert http.get("/analysis/chart-image/quota", headers=user.h).status_code == 503
        assert system_status(http, world)["chart_analysis"]["enabled"] is False
        assert http.get("/users/me", headers=user.h).status_code == 200
    finally:
        compose("up", "-d", "--no-deps", "--wait", "backend", env={"CHART_ANALYSIS_ENABLED": None})
        wait_until_ready(http)
    wait_for(
        lambda: system_status(http, world)["chart_analysis"]["enabled"], "chart analysis back on"
    )
