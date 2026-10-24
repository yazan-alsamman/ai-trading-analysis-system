"""Explanations of AI setups (B9, ``ai.explain``; docs/ai-contract.md#9-explanations).

Fadi's rule (extra 5), applied when storing **and** when serving: no unverified number ever
reaches a user.

- ``verified``: the text was checked against the setup's numbers: shown;
- not verified but ``template_used``: the fixed template filled with the setup's own numbers:
  shown;
- otherwise: not shown. The API answers ``explanation: null`` with ``explanation_status:
  "unavailable"`` and the UI shows "الشرح غير متاح" / "Explanation unavailable".

``explain`` asks ai-service ``/v1/explain`` once per setup and language (30 s timeout, the
client's retries on 5xx) and stores only an answer that may be shown. A 404 (ai-service has no
``/v1/explain`` yet, Fadi's P7) means unavailable, quietly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIContractError, AIServiceClient
from app.ai.contract import ExplainRequest, ExplainResponse, Setup
from app.models.ai import AISetup, AISetupExplanation

logger = logging.getLogger(__name__)

Status = Literal["verified", "template", "unavailable"]
UNAVAILABLE_TEXT = {"ar": "الشرح غير متاح", "en": "Explanation unavailable"}


@dataclass(frozen=True)
class Visible:
    """What a user may see of an explanation: the text (None when not shown) and why."""

    text: str | None
    status: Status


def visible(row: AISetupExplanation | ExplainResponse | None) -> Visible:
    """Fadi's rule: verified text, else the template text, else nothing."""
    if row is None:
        return Visible(None, "unavailable")
    if row.verified:
        return Visible(row.text, "verified")
    if row.template_used:
        return Visible(row.text, "template")
    return Visible(None, "unavailable")


async def stored(session: AsyncSession, setup_id: str, lang: str) -> Visible:
    """The explanation of ``setup_id`` in ``lang`` as a user may see it."""
    return visible(await session.get(AISetupExplanation, (setup_id, lang)))


async def store_answer(
    session: AsyncSession, setup_id: str, lang: str, answer: ExplainResponse
) -> Visible:
    """Store an answer only when it may be shown (the rule on storing); the first stored
    answer is kept. An unverified non-template text is logged (without the text) and dropped."""
    shown = visible(answer)
    if shown.text is None:
        logger.warning(
            "ai explain %s/%s: not verified and not a template: not stored, not shown",
            setup_id,
            lang,
        )
        return shown
    await session.execute(
        insert(AISetupExplanation)
        .values(
            setup_id=setup_id,
            lang=lang,
            text=answer.text,
            verified=answer.verified,
            template_used=answer.template_used,
        )
        .on_conflict_do_nothing(index_elements=["setup_id", "lang"])
    )
    await session.commit()
    return await stored(session, setup_id, lang)


async def explain(
    factory: async_sessionmaker[AsyncSession],
    setup_id: str,
    lang: str,
    *,
    client: AIServiceClient | None = None,
) -> str:
    """Ask ai-service for the explanation of ``setup_id`` in ``lang`` and store it.

    Returns ``stored`` (shown from now on), ``exists`` (already stored), ``unavailable``
    (404, or an answer that may not be shown) or ``missing`` (unknown setup). Raises
    ``AIUnavailableError`` after the client's retries (the task retries a bounded number of
    times) and ``AIContractError`` for another 4xx or a bad body."""
    async with factory() as session:
        if (await stored(session, setup_id, lang)).text is not None:
            return "exists"
        setup = await session.get(AISetup, setup_id)
        if setup is None:
            return "missing"
        request = ExplainRequest(setup=Setup.model_validate(setup.last_payload), lang=lang)
        own = client is None
        client = client or AIServiceClient()
        try:
            answer = await client.explain(request)
        except AIContractError as exc:
            if exc.status == 404:
                logger.info("ai explain %s/%s: ai-service has no /v1/explain yet", setup_id, lang)
                return "unavailable"
            raise
        finally:
            if own:
                await client.aclose()
        shown = await store_answer(session, setup_id, lang, answer)
        return "stored" if shown.text is not None else "unavailable"


async def for_setup(session: AsyncSession, setup_id: str) -> dict[str, Visible]:
    """Every stored language of a setup, as users may see them."""
    rows = await session.scalars(
        select(AISetupExplanation).where(AISetupExplanation.setup_id == setup_id)
    )
    return {row.lang: visible(row) for row in rows}
