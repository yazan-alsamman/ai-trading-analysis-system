"""Topic names. Always build them with these helpers, never from raw client input.

A topic is what clients subscribe to; its Redis Pub/Sub channel is ``ws:`` + topic.
"""

import uuid

from app.models.candle import Timeframe

CHANNEL_PREFIX = "ws:"


def candles_topic(instrument_id: uuid.UUID, timeframe: Timeframe) -> str:
    return f"candles:{instrument_id}:{Timeframe(timeframe).value}"


def user_topic(user_id: uuid.UUID) -> str:
    """Per-user notifications (Y15). Only that user is ever subscribed to it."""
    return f"user:{user_id}"


def signals_topic(instrument_id: uuid.UUID) -> str:
    """Strategy signals produced by the live engine for one instrument (all timeframes)."""
    return f"signals:{instrument_id}"


def private_signals_topic(instrument_id: uuid.UUID | str, user_id: uuid.UUID | None) -> str:
    """Where the signals of a **private** custom strategy are published, instead of
    ``signals:{instrument_id}``: ``signals:{instrument_id}:user:{owner}`` for its owner and
    ``signals:{instrument_id}:admins`` for admins (``user_id=None``). Clients never subscribe to
    these by name: subscribing to ``signals:{instrument_id}`` also subscribes the connection to
    its own one (admins: the admins one), and the frames carry ``topic: signals:{id}``."""
    return f"signals:{instrument_id}:" + ("admins" if user_id is None else f"user:{user_id}")


def is_private_signals(topic: str) -> bool:
    return topic.startswith("signals:") and topic.count(":") >= 2


def news_topic(instrument_id: uuid.UUID | str | None = None) -> str:
    """New articles (Y18): ``news`` gets all of them, ``news:{instrument_id}`` those tagged
    with that instrument."""
    return "news" if instrument_id is None else f"news:{instrument_id}"


def chat_topic(conversation_id: uuid.UUID | str) -> str:
    """A chat conversation (Y19): only its two participants (and admins) may subscribe."""
    return f"chat:{conversation_id}"


def ai_setups_topic(instrument_id: uuid.UUID | str) -> str:
    """AI setup state changes of one instrument (B11): public, gated by
    ``strategy_resolver.may_read_ai_setup``."""
    return f"ai:setups:{instrument_id}"


def channel_for(topic: str) -> str:
    return CHANNEL_PREFIX + topic


def topic_for(channel: str) -> str | None:
    return channel[len(CHANNEL_PREFIX) :] if channel.startswith(CHANNEL_PREFIX) else None
