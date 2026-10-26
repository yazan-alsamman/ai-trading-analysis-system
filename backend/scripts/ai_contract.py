"""Generate the ai-service contract (B7): docs/api/ai-service.openapi.yaml (OpenAPI 3.1).

    python scripts/ai_contract.py            # write the file
    python scripts/ai_contract.py --check    # exit 1 if it is out of date (CI)

The schemas come from ``app/ai/contract.py`` (pydantic only: this script needs nothing else
from the backend, so the api-contract CI job runs it with just pydantic and PyYAML). The
example payloads of docs/api/ai-service-examples/ are embedded, so they cannot drift either.
Version 0.2.0 applies Fadi's answers (docs/ai-contract.md); 0.2.1 accepts ``ok`` without a model;
0.2.2 adds ``InstrumentSpec.cost_per_unit``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = ROOT / "docs" / "api" / "ai-service.openapi.yaml"
EXAMPLES = ROOT / "docs" / "api" / "ai-service-examples"
sys.path.insert(0, str(BACKEND))

import yaml  # noqa: E402
from pydantic.json_schema import models_json_schema  # noqa: E402

from app.ai import contract as c  # noqa: E402

MODELS = [
    c.EvaluateRequest,
    c.EvaluateResponse,
    c.SizeRequest,
    c.SizeResponse,
    c.ExplainRequest,
    c.ExplainResponse,
    c.ErrorResponse,
    c.Health,
]
DESCRIPTION = """\
The stateless trading engine (ai-service, owned by Fadi). The backend owns the data,
the schedule, the storage and the delivery; ai-service decides setups and their states.

**Version 0.2.2**: Fadi's answers to the 17 open points of 0.1.0-draft are applied
(docs/ai-contract.md, section 7); 0.2.1 accepts `status: ok` with `versions.model` null; 0.2.2
adds the optional `instrument_spec.cost_per_unit` to `/v1/size`.
`/v1` changes only by adding fields; `info.version` follows semver; ai-service reports its
versions in every answer and in `/health`. Generated from
backend/app/ai/contract.py by backend/scripts/ai_contract.py (do not edit by hand).

- Every timestamp is UTC, ISO-8601 with `Z`. Every bar is closed; `ts` is its open time.
  `1d` bars are New York trading days: 17:00 to 17:00 America/New_York (DST-aware).
- The decision bar (the last bar of the smallest timeframe) always has a `spread`; without
  one the backend does not call ai-service.
- `request_id` is deterministic (`{instrument lower}-{profile}-{bar_close_ts}`): the same
  body gives a byte-identical response, and a retry always sends the same body.
- `setup_id` is deterministic and chosen by ai-service; `open_setups` echoes setups exactly as
  last returned. A response carries the current state of every setup in `new_setups` and its
  full history in `transitions` (the backend dedupes by `(setup_id, to, at)`; a state never
  goes backwards).
- Transitions: DEVELOPING -> ARMED -> ACTIVE -> CLOSED; DEVELOPING or ARMED -> EXPIRED or
  INVALIDATED. ARMED and ACTIVE may share an `at`.
- v1 has no model: the rules run alone, so `status` is `ok` with `versions.model`,
  `probability`, `ev_r`, `ev_r_lower` and `grade` null (not available, never 0).
  `grade` is A-D and always null in v1. Money is USD only in v1.
- `instrument_spec.cost_per_unit` (0.2.2, `/v1/size` only): the instrument's fixed trading
  cost per unit, price units, per round trip (XAU/USD 0.25 per oz, whatever the real
  spread). Size with a risk per unit of `|entry - sl| + cost_per_unit`; absent: none.
- Responses may carry fields this document does not list (the backend ignores them).
- 422: the request does not match the contract (never retried). 5xx, timeouts and connection
  errors are retried by the backend with the same body. A model is registered but not
  loaded: 200 with `status: model_unavailable` (nothing is stored).
"""


def example(name: str) -> Any:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def ref(model) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{model.__name__}"}


def body(model, examples: dict[str, str]) -> dict[str, Any]:
    return {
        "content": {
            "application/json": {
                "schema": ref(model),
                "examples": {key: {"value": example(name)} for key, name in examples.items()},
            }
        }
    }


ERRORS = {
    "422": {
        "description": "The request does not match the contract (FastAPI style; never retried)",
        "content": {"application/json": {"schema": ref(c.ErrorResponse)}},
    },
    "5XX": {"description": "Server error: the backend retries with the same body"},
}
REQUEST_ID = {
    "name": "X-Request-ID",
    "in": "header",
    "required": False,
    "description": "evaluate: the request_id; size/explain: the setup_id (for logs)",
    "schema": {"type": "string"},
}


def operation(op_id: str, summary: str, request, response, req_ex, resp_ex) -> dict[str, Any]:
    return {
        "post": {
            "operationId": op_id,
            "summary": summary,
            "parameters": [REQUEST_ID],
            "requestBody": {"required": True, **body(request, req_ex)},
            "responses": {"200": {"description": "OK", **body(response, resp_ex)}, **ERRORS},
        }
    }


def build() -> dict[str, Any]:
    _, schema = models_json_schema(
        [(model, "validation") for model in MODELS],
        ref_template="#/components/schemas/{model}",
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "ai-service (stateless trading engine)",
            "version": c.CONTRACT_VERSION,
            "description": DESCRIPTION,
        },
        "servers": [{"url": "http://ai-service:8001", "description": "inside the compose network"}],
        "paths": {
            "/v1/evaluate": operation(
                "evaluate",
                "Evaluate the bar that just closed: new setups, transitions, abstentions",
                c.EvaluateRequest,
                c.EvaluateResponse,
                {"intraday": "evaluate-request"},
                {
                    "ok": "evaluate-response-ok",
                    "ok_rules_only": "evaluate-response-ok-rules-only",
                    "model_unavailable": "evaluate-response-model-unavailable",
                },
            ),
            "/v1/size": operation(
                "size",
                "Position size of a setup for one account",
                c.SizeRequest,
                c.SizeResponse,
                {"xauusd": "size-request", "xauusd_fixed_cost": "size-request-fixed-cost"},
                {"xauusd": "size-response", "xauusd_fixed_cost": "size-response-fixed-cost"},
            ),
            "/v1/explain": operation(
                "explain",
                "Explain a setup in Arabic or English",
                c.ExplainRequest,
                c.ExplainResponse,
                {"arabic": "explain-request"},
                {"arabic": "explain-response"},
            ),
            "/health": {
                "get": {
                    "operationId": "health",
                    "summary": "Liveness, with the loaded versions",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": ref(c.Health)}},
                        }
                    },
                }
            },
        },
        "components": {"schemas": schema["$defs"]},
    }


def render() -> str:
    return yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if args.check:
        if current != content:
            print(f"out of date: {OUT.relative_to(ROOT)}")
            print("run: python backend/scripts/ai_contract.py")
            return 1
        print("ai-service contract up to date")
        return 0
    if current != content:
        OUT.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        print("ai-service contract unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
