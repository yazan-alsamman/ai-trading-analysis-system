"""AI assistant chat (docs/ai-chat.md)."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_MESSAGES = 20
MAX_CHARS = 2_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatTurn(_Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CHARS)


class AIChatRequest(_Strict):
    messages: list[ChatTurn] = Field(
        min_length=1,
        max_length=MAX_MESSAGES,
        description="the conversation so far, oldest first; the last one is the new question",
        examples=[[{"role": "user", "content": "What moves gold today?"}]],
    )
    language: Literal["ar", "en"] | None = Field(
        default=None, description="answer language; default: the user's notification language"
    )
    instrument_id: uuid.UUID | None = Field(
        default=None,
        description="the instrument the question is about (price context); default XAU/USD",
    )

    @model_validator(mode="after")
    def _last_is_user(self) -> Self:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be the user's question")
        if not self.messages[-1].content.strip():
            raise ValueError("the question is empty")
        return self


class AIChatQuota(BaseModel):
    limit: int
    used: int
    remaining: int
    resets_at: datetime


class AIChatUsage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class AIChatResponse(BaseModel):
    reply: str = Field(description="plain text (may contain simple Markdown: lists, bold)")
    language: Literal["ar", "en"]
    model: str
    usage: AIChatUsage
    quota: AIChatQuota
    disclaimer: str
