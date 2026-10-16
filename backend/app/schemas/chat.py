import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.chat import MESSAGE_MAX, ConversationStatus
from app.schemas.experts import PersonRef
from app.social import markdown


def _body(v: str) -> str:
    v = markdown.check(v)
    if not v:
        raise ValueError("must not be empty")
    return v


Body = Annotated[str, Field(min_length=1, max_length=MESSAGE_MAX), AfterValidator(_body)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationOpen(_Strict):
    expert_id: uuid.UUID


class MessageAttachment(_Strict):
    type: Literal["signal", "backtest", "post", "custom_strategy"]
    id: uuid.UUID


class MessageCreate(_Strict):
    body: Body
    attachments: list[MessageAttachment] = Field(default_factory=list, max_length=5)
    client_id: uuid.UUID = Field(description="made by the client; a retry with it is a no-op")


class MessageUpdate(_Strict):
    body: Body


class ReadMarker(_Strict):
    message_id: uuid.UUID | None = Field(
        default=None, description="read up to this message (default: everything)"
    )


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    body: str | None = Field(description="null when deleted")
    attachments: list[dict[str, Any]]
    client_id: uuid.UUID | None = Field(description="only for the sender")
    edited_at: datetime | None
    deleted: bool
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageRead]
    next_before: uuid.UUID | None = Field(description="pass as ?before= for older messages")


class LastMessage(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    excerpt: str | None
    created_at: datetime


class ConversationRead(BaseModel):
    id: uuid.UUID
    expert_id: uuid.UUID
    user_id: uuid.UUID
    other: PersonRef
    my_role: Literal["expert", "subscriber", "admin"]
    status: ConversationStatus
    blocked_by_me: bool
    can_send: bool
    read_only_reason: str | None
    unread: int
    last_message: LastMessage | None
    last_message_at: datetime | None
    other_last_read_at: datetime | None
    created_at: datetime
