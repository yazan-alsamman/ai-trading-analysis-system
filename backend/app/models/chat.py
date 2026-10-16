"""Expert chat (Y19): one conversation per (expert, user), messages with read markers."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

MESSAGE_MAX = 4_000


class ConversationStatus(StrEnum):
    open = "open"
    closed = "closed"
    blocked = "blocked"  # no new messages from either side


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("expert_id", "user_id", name="uq_conversations_pair"),
        Index("ix_conversations_user_last", "user_id", text("last_message_at DESC NULLS LAST")),
        Index("ix_conversations_expert_last", "expert_id", text("last_message_at DESC NULLS LAST")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(
            ConversationStatus,
            name="conversation_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ConversationStatus.open,
        server_default=ConversationStatus.open.value,
    )
    blocked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expert_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class Message(Base):
    """``client_id``: a uuid made by the client, unique per sender, so a retried send returns
    the first message instead of a duplicate. Deleting leaves a tombstone (``deleted_at``,
    empty body)."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("sender_id", "client_id", name="uq_messages_sender_client"),
        Index("ix_messages_conversation_created", "conversation_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
