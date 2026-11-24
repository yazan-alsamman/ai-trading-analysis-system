"""CI e2e step (B9): the backend's ai-service client against the fake ai-service over the compose
network, from inside the ``worker`` container (``AI_SERVICE_URL=http://fake-ai:8001``).

    docker compose cp docs/api/ai-service-examples/evaluate-request.json worker:/tmp/req.json
    docker compose cp tools/fake_ai_service/e2e_check.py worker:/tmp/e2e_check.py
    docker compose exec -T -e AI_SERVICE_URL=http://fake-ai:8001 -e AI_REQUEST_GZIP=true \\
      worker python /tmp/e2e_check.py /tmp/req.json

Checks: /health answers; evaluate returns a DEVELOPING setup with gzip bodies; the same body
gives the same answer; a 503 is retried then unavailable; a 422 is a contract error; explain
404 is a contract error with status 404 (the backend reads it as "unavailable").
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from app.ai import contract as c
from app.ai.client import AIContractError, AIServiceClient, AIUnavailableError
from app.core.config import get_settings


async def main(path: str) -> None:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    base = get_settings().ai_service_url
    async with httpx.AsyncClient(base_url=base) as http:
        for _ in range(30):  # the fake starts in a second or two
            try:
                if (await http.get("/health")).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(1)
        else:
            raise SystemExit(f"fake ai-service not reachable at {base}")
        await http.post("/_fake/reset")
        req = c.EvaluateRequest.model_validate(raw)
        async with AIServiceClient(backoff=0) as ai:
            first = await ai.evaluate(req)
            again = await ai.evaluate(req)
            assert first.status == c.EvaluateStatus.ok, first
            assert [s.state for s in first.new_setups] == [c.SetupState.DEVELOPING]
            assert first.model_dump(mode="json") == again.model_dump(mode="json")
            received = (await http.get("/_fake/requests")).json()
            assert all(r["gzip"] for r in received), received
            await http.post("/_fake/mode", json={"evaluate": "503"})
            try:
                await ai.evaluate(req)
                raise AssertionError("503 must be unavailable")
            except AIUnavailableError as exc:
                assert exc.attempts == get_settings().ai_max_retries + 1
            await http.post("/_fake/mode", json={"evaluate": "422"})
            try:
                await ai.evaluate(req)
                raise AssertionError("422 must be a contract error")
            except AIContractError as exc:
                assert exc.status == 422
            explain = c.ExplainRequest(setup=first.new_setups[0], lang="en")
            try:
                await ai.explain(explain)
                raise AssertionError("explain must be 404 by default")
            except AIContractError as exc:
                assert exc.status == 404
    print(f"fake ai-service e2e ok ({len(received)} gzip evaluate bodies)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
