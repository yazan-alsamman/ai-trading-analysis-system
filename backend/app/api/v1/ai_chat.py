"""AI assistant chat (docs/ai-chat.md). JWT only."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.limits import COST_KEY
from app.assistant import chat
from app.core.config import get_settings
from app.core.redis import get_redis
from app.schemas.ai_chat import AIChatQuota, AIChatRequest, AIChatResponse
from app.vision.service import default_language

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])


@router.post(
    "",
    response_model=AIChatResponse,
    openapi_extra={COST_KEY: get_settings().ai_chat_cost},
    responses={
        422: {"description": "invalid conversation, or `blocked` / `empty_answer`"},
        429: {"description": "`quota_exceeded` (daily) with Retry-After, or the rate limit"},
        503: {
            "description": "`not_configured`, `model_busy`, `model_unavailable`, `timeout` "
            "(Retry-After)"
        },
    },
)
async def ask(data: AIChatRequest, user: CurrentUser, session: SessionDep):
    """Ask the AI assistant. Send the whole conversation (at most 20 turns) each time; nothing
    is stored. The answer uses the platform's live context (price, news sentiment and headlines,
    upcoming high-impact USD events) and is educational, not investment advice. One unit of the
    daily quota per answer (`GET /ai/chat/quota`); a failed model call does not count."""
    chat.require_enabled()
    language = data.language or await default_language(session, user)
    messages = [m.model_dump() for m in data.messages]
    return await chat.answer(session, get_redis(), user, messages, language, data.instrument_id)


@router.get("/quota", response_model=AIChatQuota)
async def ask_quota(user: CurrentUser):
    """Questions left today (UTC day)."""
    return await chat.quota(get_redis(), user)
