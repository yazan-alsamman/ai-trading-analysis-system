"""The LLM behind the explanations (P7 F3, ``docs/phase7/PLAN.md``): a thin provider interface.

Today one provider, Gemini (``gemini-3.6-flash``, Fadi 2026-11-13), through Google's official
``google-genai`` SDK, as the backend's chart analysis (``../docs/chart-analysis.md``). A provider
answers one question: given a system instruction and a request, the text, or ``None`` when it has
none (no key, a timeout, an error, a refusal, an empty or malformed answer). It never raises: the
caller then falls back to the template.

Settings (environment): ``GEMINI_API_KEY`` (none: no LLM, the template only), ``GEMINI_MODEL``
(default ``gemini-3.6-flash``), ``EXPLAIN_LLM_TIMEOUT_SECONDS`` (default 20, one attempt; the
contract allows 30 s per attempt and the backend retries). Logged: provider, model, latency,
tokens, and why there is no text. Never the key, the request or the answer."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from functools import cache
from typing import Any, Protocol

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.6-flash"
TEMPERATURE = 0.2
MAX_OUTPUT_TOKENS = 2048  # the answer is about 150 words; thinking is billed as output too
OK_FINISH = {"STOP", "FINISH_REASON_UNSPECIFIED"}


class Answer(BaseModel):
    """The structured answer asked of the model: one field, the explanation."""

    text: str


@dataclass(frozen=True)
class Reply:
    text: str | None
    model: str
    why_none: str | None = None
    latency_ms: int = 0


class LLM(Protocol):
    name: str

    def write(self, system: str, request: str) -> Reply: ...


class Gemini:
    name = "gemini"

    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, timeout_s: float = 20.0, client: Any = None
    ):
        self.model = model
        self._key = api_key
        self._timeout_ms = int(timeout_s * 1000)
        self._client = client

    def client(self) -> Any:
        if self._client is None:
            from google import genai  # loaded only when an explanation is asked for
            from google.genai import types

            self._client = genai.Client(
                api_key=self._key,
                http_options=types.HttpOptions(
                    timeout=self._timeout_ms, retry_options=types.HttpRetryOptions(attempts=1)
                ),
            )
        return self._client

    def write(self, system: str, request: str) -> Reply:
        from google.genai import types

        t0 = time.monotonic()
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=Answer,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )
        try:
            resp = self.client().models.generate_content(
                model=self.model, contents=request, config=config
            )
        except Exception as e:  # network, timeout, 4xx / 5xx: the template answers
            return self._none(f"error: {type(e).__name__}", t0)
        text, why = parse(resp)
        ms = int((time.monotonic() - t0) * 1000)
        usage = getattr(resp, "usage_metadata", None)
        logger.info(
            "explain llm model=%s ms=%d in=%s out=%s why_none=%s",
            self.model,
            ms,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            why,
        )
        return Reply(text, self.model, why, ms)

    def _none(self, why: str, t0: float) -> Reply:
        ms = int((time.monotonic() - t0) * 1000)
        logger.info("explain llm model=%s ms=%d why_none=%s", self.model, ms, why)
        return Reply(None, self.model, why, ms)


def _name(v: Any) -> str | None:
    return None if v is None else (getattr(v, "name", None) or str(v))


def parse(resp: Any) -> tuple[str | None, str | None]:
    """(text, None) or (None, why): blocked, a stop other than a normal one, no structured
    answer, or an empty text."""
    fb = getattr(resp, "prompt_feedback", None)
    blocked = _name(getattr(fb, "block_reason", None)) if fb else None
    if blocked and blocked != "BLOCKED_REASON_UNSPECIFIED":
        return None, f"blocked: {blocked}"
    cands = getattr(resp, "candidates", None) or []
    finish = _name(getattr(cands[0], "finish_reason", None)) if cands else None
    if finish and finish not in OK_FINISH:
        return None, f"finish: {finish}"
    parsed = getattr(resp, "parsed", None)
    if parsed is None:
        return None, "no structured answer"
    data = parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
    text = (data or {}).get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None, "empty text"
    return text.strip(), None


@cache
def default() -> LLM | None:
    """The configured provider, or ``None`` (no key: the template only)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = float(os.environ.get("EXPLAIN_LLM_TIMEOUT_SECONDS", "20"))
    return Gemini(key, model, timeout)
