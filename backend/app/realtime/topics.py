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


def news_topic(instrument_id: uuid.UUID | str | None = None) -> str:
    """New articles (Y18): ``news`` gets all of them, ``news:{instrument_id}`` those tagged
    with that instrument."""
    return "news" if instrument_id is None else f"news:{instrument_id}"


def channel_for(topic: str) -> str:
    return CHANNEL_PREFIX + topic


def topic_for(channel: str) -> str | None:
    return channel[len(CHANNEL_PREFIX) :] if channel.startswith(CHANNEL_PREFIX) else None
