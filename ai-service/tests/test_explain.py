"""The explanation template and the number checker (app/agent): every template verified, every
planted wrong number caught, the endpoint against the contract."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent import explain as ex
from app.agent import llm as llm_mod
from app.agent import verify as vf
from app.agent.explain import explain_setup, template
from app.live import gold_levels as lv
from tests.test_gold_levels_live import day_at, frames
from tests.test_main import body, client

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api" / "ai-service-examples"
VOL = {
    "status": "ok",
    "model": "vol-m3-15m-v1",
    "day": "2025-04-02",
    "window": "02:00-16:45 America/New_York",
    "expected_move_pct": 0.951,
    "range_pct": {"p20": 1.01, "p50": 1.345, "p80": 1.873},
    "range_usd": {"p20": 29.34, "p50": 39.11, "p80": 54.44},
    "level": "lively",
    "news": [{"ts": "2025-04-02T12:30:00Z", "ts_ny": "08:30", "title": "CPI m/m", "top3": True}],
}


def gold_setups() -> list[dict]:
    out = []
    for hhmm in ("09:30", "16:55"):
        t = day_at(20250402, hhmm)
        for s in lv.scan_day(frames(t), t):
            p = lv.payload(s, "XAUUSD", "gold_levels")
            p["evidence"] = dict(p["evidence"], volatility=VOL)
            out.append(p)
    return out


def test_tokens_read_arabic_digits_separators_and_times() -> None:
    t = vf.tokens("الدخول ٤٣٤٩٫٠٣ والوقف 4,329.38 الساعة 16:45 بنسبة 0.95%")
    assert [x.value for x in t] == [4349.03, 4329.38, 16, 45, 0.95]
    assert [x.decimals for x in t] == [2, 2, 0, 0, 2]


def test_matching_rules() -> None:
    src = {"d": 19.646619, "rule": "0.75 x ATR(14, 4h)", "price": 4349.03}
    assert not vf.unverified("D = 19.65 (0.75 x ATR(14, 4h)), level 4349", src)
    assert vf.unverified("D = 19.66", src) == ["19.66"]
    assert vf.unverified("R 20", src) == ["20"]  # 19.65 does not round to a whole 20


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_every_gold_template_is_verified(lang: str) -> None:
    setups = gold_setups()
    states = {s["state"] for s in setups}
    assert {"ARMED", "ACTIVE", "CLOSED", "EXPIRED"} <= states
    assert states <= {"ARMED", "ACTIVE", "CLOSED", "EXPIRED", "INVALIDATED"}
    for s in setups:
        out = explain_setup(s, lang)
        assert out["verified"] and out["template_used"], (s["setup_id"], out["text"])
        assert "08:30" in out["text"] and "39.11" in out["text"]


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_every_planted_wrong_number_is_caught(lang: str) -> None:
    caught = planted = 0
    for s in gold_setups()[:12]:
        text, sources = template(s, lang)
        vals = vf.allowed(*sources)
        for tok in vf.tokens(text):
            wrong = round(tok.value + 0.37 + (1 if tok.decimals == 0 else 0), tok.decimals)
            new = f"{wrong:.{tok.decimals}f}"
            if vf.matches(vf.Token(new, wrong, tok.decimals), vals):
                continue  # the changed number happens to be another allowed one
            planted += 1
            bad = text.replace(tok.text, new, 1)
            caught += bool(vf.unverified(bad, *sources))
    assert planted > 100 and caught == planted


def test_the_contract_example_and_an_l1_setup() -> None:
    req = json.loads((EXAMPLES / "explain-request.json").read_text(encoding="utf-8"))
    r = client.post("/v1/explain", json=req)
    assert r.status_code == 200
    out = r.json()
    assert out["verified"] and out["template_used"] and "2400.00" in out["text"]
    setup = client.post("/v1/evaluate", json=body()).json()["new_setups"][0]
    for lang in ("ar", "en"):
        out = client.post("/v1/explain", json={"setup": setup, "lang": lang}).json()
        assert out["verified"] and "SMC" in out["text"]
        assert (
            ("لم يُثبت البحث" in out["text"])
            if lang == "ar"
            else ("did not find an edge" in out["text"])
        )


# --- F3: the LLM in front of the template ---------------------------------------------------------


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """CI never calls Gemini: no key, and the cached provider cleared."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    llm_mod.default.cache_clear()
    yield
    llm_mod.default.cache_clear()


class Fake:
    name = "fake"

    def __init__(self, text):
        self.text = text
        self.calls = []

    def write(self, system, request):
        self.calls.append((system, request))
        return llm_mod.Reply(self.text, "fake")


def one_gold(state="ARMED") -> dict:
    return next(s for s in gold_setups() if s["state"] == state)


def rewrite(s: dict, lang: str) -> str:
    """A good rewrite: the template's facts in another order, the required ending kept."""
    text, _ = ex.template(s, lang)
    body_, end = text[: -len(ex.NOT_ADVICE[lang])].strip(), ex.NOT_ADVICE[lang]
    return ("باختصار، " if lang == "ar" else "In short, ") + body_ + " " + end


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_a_good_llm_text_is_shown(lang) -> None:
    s = one_gold()
    fake = Fake(rewrite(s, lang))
    out = ex.explain_setup(s, lang, fake)
    assert out == {"text": fake.text, "verified": True, "template_used": False}
    system, request = fake.calls[0]
    assert system == ex.system_prompt() and "REFERENCE TEXT" in request and "LVL4H" in request


@pytest.mark.parametrize(
    "spoil",
    [
        lambda t, lang: t.replace(ex.NOT_ADVICE[lang], ""),  # ending missing
        lambda t, lang: t.replace(
            ex.NOT_ADVICE[lang], "9999.99 " + ex.NOT_ADVICE[lang]
        ),  # invented
        lambda t, lang: ("ننصح بالدخول. " if lang == "ar" else "We recommend it. ") + t,  # advice
        lambda t, lang: "**" + t,  # markdown
        lambda t, lang: t.replace("LVL4H", "XX"),  # strategy name lost
    ],
)
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_a_bad_llm_text_falls_back_to_the_template(spoil, lang) -> None:
    s = one_gold()
    out = ex.explain_setup(s, lang, Fake(spoil(rewrite(s, lang), lang)))
    assert out["template_used"] and out["verified"]
    assert out["text"] == ex.template(s, lang)[0]


def test_wrong_language_and_no_answer_fall_back() -> None:
    s = one_gold()
    assert ex.explain_setup(s, "ar", Fake(rewrite(s, "en")))["template_used"]
    assert ex.explain_setup(s, "ar", Fake(None))["template_used"]


def test_l1_needs_the_unvalidated_ending() -> None:
    setup = client.post("/v1/evaluate", json=body()).json()["new_setups"][0]
    text, _ = ex.template(setup, "en")
    assert text.endswith(ex.required_ending(setup, "en"))
    good = "In short, " + text
    assert not ex.explain_setup(setup, "en", Fake(good))["template_used"]
    short = good.replace(ex.UNVALIDATED["en"], "")
    assert ex.explain_setup(setup, "en", Fake(short))["template_used"]


def test_no_key_means_no_llm() -> None:
    assert llm_mod.default() is None
    s = one_gold()
    assert ex.explain_setup(s, "ar")["template_used"]


def test_parse_the_model_answer() -> None:
    ok = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason="STOP")],
        parsed=llm_mod.Answer(text=" hello "),
    )
    assert llm_mod.parse(ok) == ("hello", None)
    blocked = SimpleNamespace(prompt_feedback=SimpleNamespace(block_reason="SAFETY"), candidates=[])
    assert llm_mod.parse(blocked)[0] is None
    safety = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason="SAFETY")],
        parsed={"text": "x"},
    )
    assert llm_mod.parse(safety) == (None, "finish: SAFETY")
    empty = SimpleNamespace(prompt_feedback=None, candidates=[], parsed={"text": "  "})
    assert llm_mod.parse(empty) == (None, "empty text")


def test_gemini_never_raises() -> None:
    class Broken:
        class models:  # noqa: N801
            @staticmethod
            def generate_content(**kw):
                raise TimeoutError("slow")

    class Works:
        class models:  # noqa: N801
            @staticmethod
            def generate_content(**kw):
                assert kw["model"] == "gemini-3.6-flash" and kw["config"].temperature == 0.2
                return SimpleNamespace(
                    prompt_feedback=None,
                    candidates=[],
                    parsed={"text": "ok text"},
                    usage_metadata=None,
                )

    assert llm_mod.Gemini("k", client=Broken()).write("s", "r").why_none == "error: TimeoutError"
    assert llm_mod.Gemini("k", client=Works()).write("s", "r").text == "ok text"
