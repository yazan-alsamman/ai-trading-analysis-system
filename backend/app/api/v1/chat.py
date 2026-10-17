"""Expert chat (docs/chat.md). REST here; live delivery on the WebSocket topic
``chat:{conversation_id}``. JWT only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.chat import service
from app.core.redis import get_redis
from app.models.chat import ConversationStatus
from app.schemas.chat import (
    ConversationOpen,
    ConversationRead,
    MessageCreate,
    MessagePage,
    MessageRead,
    MessageUpdate,
    ReadMarker,
)
from app.schemas.common import Page

router = APIRouter(tags=["chat"])
admin_router = APIRouter(prefix="/admin/conversations", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(user: CurrentUser, session: SessionDep):
    """Your conversations (as subscriber or expert), most recent first."""
    return await service.list_conversations(session, user)


@router.post("/conversations", response_model=ConversationRead, status_code=201)
async def open_conversation(
    data: ConversationOpen, user: CurrentUser, session: SessionDep, response: Response
):
    """Open (201) or return (200) your conversation with an expert. Needs a subscription with
    the ``chat`` perk (403)."""
    conv, created = await service.open_conversation(session, user, data.expert_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return await service.read_conversation(session, user, conv)


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    conv = await service.conversation_for(session, user, conversation_id)
    return await service.read_conversation(session, user, conv)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
async def history(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    before: Annotated[uuid.UUID | None, Query(description="a message id (exclusive)")] = None,
    limit: Annotated[int, Query(ge=1, le=service.HISTORY_MAX)] = 50,
):
    """Newest first; pass ``next_before`` as ``before`` for older messages."""
    conv = await service.conversation_for(session, user, conversation_id)
    items, next_before = await service.history(session, user, conv, before=before, limit=limit)
    return MessagePage(items=items, next_before=next_before)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    user: CurrentUser,
    session: SessionDep,
    response: Response,
):
    """201 with the new message, or 200 with the first one for a repeated ``client_id``.
    403 read-only or blocked, 422 invalid body or attachment, 429 over the chat limits."""
    conv = await service.conversation_for(session, user, conversation_id)
    message, created = await service.send(session, get_redis(), user, conv, data)
    if not created:
        response.status_code = status.HTTP_200_OK
    return (await service.serialize(session, user, [message]))[0]


@router.patch("/messages/{message_id}", response_model=MessageRead)
async def edit_message(
    message_id: uuid.UUID, data: MessageUpdate, user: CurrentUser, session: SessionDep
):
    """The sender, within 15 minutes."""
    message = await service.own_message(session, user, message_id)
    message = await service.edit(session, get_redis(), user, message, data.body)
    return (await service.serialize(session, user, [message]))[0]


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """The sender: a tombstone stays in the history."""
    message = await service.own_message(session, user, message_id)
    await service.delete(session, get_redis(), user, message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/read")
async def mark_read(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    data: ReadMarker | None = None,
) -> dict:
    """Move your read marker (to a message, or to now); the other side gets ``chat_read``."""
    conv = await service.conversation_for(session, user, conversation_id)
    at = await service.mark_read(
        session, get_redis(), user, conv, data.message_id if data else None
    )
    return {"conversation_id": str(conv.id), "read_at": at.isoformat()}


@router.post("/conversations/{conversation_id}/block", response_model=ConversationRead)
async def block(conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Either side: no new messages from anyone until the side that blocked unblocks."""
    conv = await service.conversation_for(session, user, conversation_id)
    conv = await service.block(session, user, conv, True)
    return await service.read_conversation(session, user, conv)


@router.post("/conversations/{conversation_id}/unblock", response_model=ConversationRead)
async def unblock(conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    conv = await service.conversation_for(session, user, conversation_id)
    conv = await service.block(session, user, conv, False)
    return await service.read_conversation(session, user, conv)


@admin_router.get("")
async def admin_conversations(
    _: AdminUser,
    session: SessionDep,
    status_: Annotated[ConversationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[dict]:
    """E.g. ``status=blocked``. Admins read any conversation through the normal endpoints."""
    items, total = await service.admin_conversations(
        session, status_=status_, limit=limit, offset=offset
    )
    return Page[dict](items=items, total=total, limit=limit, offset=offset)
