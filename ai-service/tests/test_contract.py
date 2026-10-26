"""P6 task 1: the vendored B7 contract (``app/contract.py``) is the backend's file unchanged, and
every example payload parses and serialises back to the same JSON."""

import json
from pathlib import Path

import pytest

from app import contract as c

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "docs" / "api" / "ai-service-examples"
BACKEND_CONTRACT = REPO / "backend" / "app" / "ai" / "contract.py"
MODELS = {
    "evaluate-request": c.EvaluateRequest,
    "evaluate-response-ok": c.EvaluateResponse,
    "evaluate-response-ok-rules-only": c.EvaluateResponse,
    "evaluate-response-model-unavailable": c.EvaluateResponse,
    "size-request": c.SizeRequest,
    "size-response": c.SizeResponse,
    "size-request-fixed-cost": c.SizeRequest,
    "size-response-fixed-cost": c.SizeResponse,
    "explain-request": c.ExplainRequest,
    "explain-response": c.ExplainResponse,
}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def test_vendored_contract_is_unchanged() -> None:
    if not BACKEND_CONTRACT.exists():
        pytest.skip("backend not in this checkout")
    vendored = Path(c.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert vendored == BACKEND_CONTRACT.read_bytes().replace(b"\r\n", b"\n")


def test_every_example_is_checked() -> None:
    assert {p.stem for p in EXAMPLES.glob("*.json")} == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_examples_round_trip(name: str) -> None:
    payload = load(name)
    parsed = MODELS[name].model_validate(payload)
    assert parsed.model_dump(mode="json", exclude_unset=True) == payload


def test_v1_answer_without_a_model_is_valid() -> None:
    """Open point 1 of the P6 plan: v1 answers ``ok`` with ``versions.model`` null."""
    resp = c.EvaluateResponse.model_validate(
        {
            "request_id": "xauusd-intraday-2026-10-19T14:15:00Z",
            "status": "ok",
            "versions": {"strategy": "L1", "model": None, "features": "f"},
            "abstentions": [{"reason": "no_pattern"}],
        }
    )
    assert resp.status == c.EvaluateStatus.ok and resp.versions.model is None
