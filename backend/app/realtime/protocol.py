"""Message formats of /ws/market (see docs/websocket.md)."""

import json
import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.models.candle import Timeframe

# --- client -> server -----------------------------------------------------------------------


class _ClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _TopicRef(_ClientMessage):
    topic: Literal["candles", "user"]
    instrument_id: uuid.UUID | None = None
    timeframe: Timeframe | None = None
    user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> Self:
        if self.topic == "candles":
            if self.instrument_id is None or self.timeframe is None or self.user_id is not None:
                raise ValueError("candles topic needs instrument_id and timeframe")
        elif self.user_id is None or self.instrument_id is not None or self.timeframe is not None:
            raise ValueError("user topic needs user_id")
        return self


class SubscribeMessage(_TopicRef):
    op: Literal["subscribe"]


class UnsubscribeMessage(_TopicRef):
    op: Literal["unsubscribe"]


class PingMessage(_ClientMessage):
    op: Literal["ping"]


ClientMessage = Annotated[
    SubscribeMessage | UnsubscribeMessage | PingMessage, Field(discriminator="op")
]
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


# --- server -> client -----------------------------------------------------------------------
# Error codes sent in {"type": "error", "code": ...}
BAD_REQUEST = "bad_request"
UNKNOWN_INSTRUMENT = "unknown_instrument"
INACTIVE_INSTRUMENT = "inactive_instrument"
FORBIDDEN = "forbidden"
TOO_MANY_SUBSCRIPTIONS = "too_many_subscriptions"
TOKEN_EXPIRED = "token_expired"
UNAVAILABLE = "unavailable"


def dump(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"))


def subscribed(topic: str) -> str:
    return dump({"type": "subscribed", "topic": topic})


def unsubscribed(topic: str) -> str:
    return dump({"type": "unsubscribed", "topic": topic})


def snapshot(topic: str, candle: dict[str, Any] | None) -> str:
    return dump({"type": "snapshot", "topic": topic, "candle": candle})


def pong() -> str:
    return dump({"type": "pong"})


def heartbeat() -> str:
    return dump({"type": "heartbeat"})


def error(code: str, message: str) -> str:
    return dump({"type": "error", "code": code, "message": message})


def candle_event(
    instrument_id: uuid.UUID, timeframe: Timeframe, candle: dict[str, Any]
) -> dict[str, Any]:
    """Payload of a live candle update (the publisher adds ``topic`` and ``sent_at``)."""
    return {
        "type": "candle",
        "instrument_id": str(instrument_id),
        "timeframe": Timeframe(timeframe).value,
        "candle": candle,
    }
