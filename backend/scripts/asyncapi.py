"""Generate the WebSocket contract (T07): docs/api/asyncapi.yaml (AsyncAPI 3.0) for /ws/market.

    python scripts/asyncapi.py            # write the file
    python scripts/asyncapi.py --check    # exit 1 if it is out of date (CI)

Client messages are generated from the protocol models (``app/realtime/protocol.py``), and so
are the payload parts that have a model (candles, notifications, chat messages); the other
server messages are described here. Topics are modelled as channels multiplexed over the one
socket: a client subscribes with ``{"op": "subscribe", ...}`` and the server stamps every
message with its ``topic``. CI validates the file with the AsyncAPI CLI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = ROOT / "docs" / "api" / "asyncapi.yaml"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("ENVIRONMENT", "development")
os.chdir(BACKEND / "scripts")

import yaml  # noqa: E402
from pydantic import TypeAdapter  # noqa: E402

from app.realtime import protocol  # noqa: E402
from app.schemas.chat import MessageRead  # noqa: E402
from app.schemas.market import CandleOut  # noqa: E402
from app.schemas.notifications import NotificationRead  # noqa: E402

UUID = {"type": "string", "format": "uuid"}
TS_MS = {"type": "integer", "description": "server publish time, unix milliseconds"}


def model_schema(model) -> dict[str, Any]:
    """A self-contained JSON Schema of a Pydantic model ($defs inlined into components)."""
    schema = TypeAdapter(model).json_schema(ref_template="#/components/schemas/{model}")
    for name, sub in schema.pop("$defs", {}).items():
        DEFS[name] = sub
    return schema


DEFS: dict[str, Any] = {}


def obj(required: list[str], props: dict[str, Any], description: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"type": "object", "required": required, "properties": props}
    if description:
        out["description"] = description
    return out


def typed(name: str, props: dict[str, Any], required: list[str], description: str) -> dict:
    return obj(
        ["type", *required],
        {"type": {"const": name}, "topic": {"type": "string"}, "sent_at": TS_MS, **props},
        description,
    )


SIGNAL = obj(
    ["id", "instrument_id", "timeframe", "strategy_key", "side", "price", "bar_time"],
    {
        "id": UUID,
        "instrument_id": UUID,
        "timeframe": {"type": "string", "enum": ["1m", "5m", "15m", "1h", "4h", "1d"]},
        "strategy_key": {"type": "string", "examples": ["rsi_reversal", "custom:<uuid>"]},
        "params": {"type": "object"},
        "params_hash": {"type": "string"},
        "time": {"type": "integer", "description": "bar start, unix seconds"},
        "bar_time": {"type": "string", "format": "date-time"},
        "side": {"type": "string", "enum": ["buy", "sell"]},
        "strength": {"type": "number"},
        "price": {"type": "number"},
        "reason": {"type": "string"},
        "details": {"type": "object"},
    },
)
ARTICLE = obj(
    ["id", "url", "title", "published_at", "instruments"],
    {
        "id": UUID,
        "source": obj(["key", "name"], {"key": {"type": "string"}, "name": {"type": "string"}}),
        "url": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": ["string", "null"]},
        "image_url": {"type": ["string", "null"]},
        "language": {"type": ["string", "null"]},
        "published_at": {"type": "string", "format": "date-time"},
        "sentiment": {
            "anyOf": [
                {"type": "null"},
                obj(["label"], {"label": {"type": "string"}, "score": {"type": "number"}}),
            ]
        },
        "instruments": {
            "type": "array",
            "items": obj(
                ["instrument_id", "symbol"],
                {
                    "instrument_id": UUID,
                    "symbol": {"type": "string"},
                    "relevance": {"type": "number"},
                },
            ),
        },
    },
)


def build() -> dict[str, Any]:
    candle = model_schema(CandleOut)
    notification = model_schema(NotificationRead)
    chat_message = model_schema(MessageRead)
    client = {
        "Subscribe": (
            protocol.SubscribeMessage,
            "Subscribe to a topic. candles: instrument_id + timeframe; signals: instrument_id; "
            "user: user_id (your own; automatic anyway); news: optional instrument_id; chat: "
            "conversation_id (participants and admins only). Answer: subscribed (+ snapshot "
            "for candles) or error.",
        ),
        "Unsubscribe": (protocol.UnsubscribeMessage, "Same fields as subscribe."),
        "Ping": (protocol.PingMessage, "Keep-alive; answered with pong."),
        "Typing": (
            protocol.TypingMessage,
            "Ephemeral typing indicator in a chat you are subscribed to (forwarded as "
            "chat_typing, at most once per 3 s per user).",
        ),
    }
    messages: dict[str, Any] = {}
    for name, (model, description) in client.items():
        messages[name] = {
            "name": name,
            "title": name,
            "summary": description,
            "contentType": "application/json",
            "payload": model_schema(model),
        }
    server = {
        "Subscribed": typed("subscribed", {}, ["topic"], "A subscribe was accepted."),
        "Unsubscribed": typed("unsubscribed", {}, ["topic"], "An unsubscribe was done."),
        "Snapshot": typed(
            "snapshot",
            {"candle": {"anyOf": [{"type": "null"}, candle]}},
            ["topic", "candle"],
            "The latest candle right after subscribing to a candles topic.",
        ),
        "Pong": typed("pong", {}, [], "Answer to ping."),
        "Heartbeat": typed("heartbeat", {}, [], "Sent every 25 s; no answer needed."),
        "Error": typed(
            "error",
            {
                "code": {
                    "type": "string",
                    "enum": [
                        protocol.BAD_REQUEST,
                        protocol.UNKNOWN_INSTRUMENT,
                        protocol.INACTIVE_INSTRUMENT,
                        protocol.FORBIDDEN,
                        protocol.TOO_MANY_SUBSCRIPTIONS,
                        protocol.TOKEN_EXPIRED,
                        protocol.UNAVAILABLE,
                    ],
                },
                "message": {"type": "string"},
            },
            ["code", "message"],
            "A rejected client message; the socket stays open (token_expired closes it).",
        ),
        "Candle": typed(
            "candle",
            {"instrument_id": UUID, "timeframe": {"type": "string"}, "candle": candle},
            ["instrument_id", "timeframe", "candle"],
            "Live update of the current candle (at most one per publish).",
        ),
        "Signal": typed("signal", {"signal": SIGNAL}, ["signal"], "A live strategy signal."),
        "UserSignal": typed(
            "signal",
            {
                "signal": SIGNAL,
                "user_strategy_ids": {"type": "array", "items": UUID},
                "plan": {"type": ["object", "null"], "description": "your trade plan"},
                "plans": {"type": "array", "items": {"type": "object"}},
            },
            ["signal", "user_strategy_ids"],
            "A signal of one of your active strategies (notify=true), with your trade plans.",
        ),
        "Notification": typed(
            "notification",
            {"notification": notification},
            ["notification"],
            "Every inbox notification (signals, backtests, security, posts, alerts, chat, "
            "subscriptions). A batched one (likes, chat) arrives again with the same id.",
        ),
        "BacktestProgress": typed(
            "backtest_progress",
            {
                "backtest_id": UUID,
                "status": {"type": "string"},
                "progress": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            ["backtest_id", "status", "progress"],
            "Progress of one of your backtests.",
        ),
        "BacktestCompleted": typed(
            "backtest_completed",
            {"backtest_id": UUID, "status": {"const": "completed"}, "metrics": {"type": "object"}},
            ["backtest_id", "status"],
            "Your backtest finished.",
        ),
        "BacktestFailed": typed(
            "backtest_failed",
            {"backtest_id": UUID, "status": {"const": "failed"}, "error": {"type": "string"}},
            ["backtest_id", "status"],
            "Your backtest failed.",
        ),
        "WorkspaceUpdated": typed(
            "workspace_updated",
            {
                "workspace_id": {"anyOf": [UUID, {"type": "null"}]},
                "version": {"type": ["integer", "null"]},
                "action": {
                    "type": "string",
                    "enum": [
                        "created",
                        "state_updated",
                        "renamed",
                        "default_changed",
                        "deleted",
                        "reordered",
                        "shared",
                        "unshared",
                    ],
                },
            },
            ["action"],
            "One of your workspaces changed on another device.",
        ),
        "PriceAlert": typed(
            "price_alert",
            {
                "notification_id": UUID,
                "alert_id": UUID,
                "instrument": {"type": "object"},
                "condition": {"type": "string"},
                "value": {"type": "number"},
                "price": {"type": "number"},
                "bar_time": {"type": "string", "format": "date-time"},
                "note": {"type": ["string", "null"]},
            },
            ["notification_id", "alert_id", "price", "bar_time"],
            "One of your price alerts fired.",
        ),
        "News": typed("news", {"article": ARTICLE}, ["article"], "A new article."),
        "ChatMessage": typed(
            "chat_message",
            {"conversation_id": UUID, "message": chat_message},
            ["conversation_id", "message"],
            "A new message in the conversation.",
        ),
        "ChatMessageUpdated": typed(
            "chat_message_updated",
            {"conversation_id": UUID, "message": chat_message},
            ["conversation_id", "message"],
            "A message was edited or deleted (tombstone: deleted=true, body=null).",
        ),
        "ChatRead": typed(
            "chat_read",
            {"conversation_id": UUID, "user_id": UUID, "read_at": {"type": "string"}},
            ["conversation_id", "user_id", "read_at"],
            "A participant moved their read marker.",
        ),
        "ChatTyping": typed(
            "chat_typing",
            {"conversation_id": UUID, "user_id": UUID},
            ["conversation_id", "user_id"],
            "A participant is typing (both sides receive it; ignore your own user_id).",
        ),
    }
    for name, payload in server.items():
        messages[name] = {
            "name": name,
            "title": name,
            "summary": payload.pop("description"),
            "contentType": "application/json",
            "payload": payload,
        }

    def refs(*names: str) -> dict[str, Any]:
        return {n: {"$ref": f"#/components/messages/{n}"} for n in names}

    def param(description: str) -> dict[str, Any]:
        return {"description": description}

    channels = {
        "socket": {
            "address": "/ws/market",
            "title": "The WebSocket connection",
            "description": (
                "One connection carries every topic. Authenticate with ?token=<access JWT> or "
                "?api_key=<key with the stream scope>; refused connections are closed with 4401 "
                "(4429 over the connection limits). At most 50 topic subscriptions per "
                "connection, 4 KB per client frame; idle 75 s closes with 1001; a client that "
                "falls 256 messages behind is closed with 1013."
            ),
            "messages": refs(
                "Subscribe",
                "Unsubscribe",
                "Ping",
                "Typing",
                "Subscribed",
                "Unsubscribed",
                "Snapshot",
                "Pong",
                "Heartbeat",
                "Error",
            ),
            "bindings": {
                "ws": {
                    "query": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "access JWT"},
                            "api_key": {"type": "string", "description": "tk_... (stream)"},
                        },
                    },
                    "bindingVersion": "0.1.0",
                }
            },
        },
        "candles": {
            "address": "candles:{instrument_id}:{timeframe}",
            "title": "candles topic",
            "parameters": {
                "instrument_id": param("instrument id"),
                "timeframe": {"enum": ["1m", "5m", "15m", "1h", "4h", "1d"]},
            },
            "messages": refs("Candle"),
        },
        "signals": {
            "address": "signals:{instrument_id}",
            "title": "signals topic",
            "parameters": {"instrument_id": param("instrument id")},
            "messages": refs("Signal"),
        },
        "user": {
            "address": "user:{user_id}",
            "title": "user topic (automatic, own user only)",
            "parameters": {"user_id": param("your user id")},
            "messages": refs(
                "UserSignal",
                "Notification",
                "BacktestProgress",
                "BacktestCompleted",
                "BacktestFailed",
                "WorkspaceUpdated",
                "PriceAlert",
            ),
        },
        "news": {
            "address": "news",
            "title": "news topic (all articles; API keys need news:read)",
            "messages": refs("News"),
        },
        "newsInstrument": {
            "address": "news:{instrument_id}",
            "title": "news topic of one instrument",
            "parameters": {"instrument_id": param("instrument id")},
            "messages": refs("News"),
        },
        "chat": {
            "address": "chat:{conversation_id}",
            "title": "chat topic (participants and admins)",
            "parameters": {"conversation_id": param("conversation id")},
            "messages": refs("ChatMessage", "ChatMessageUpdated", "ChatRead", "ChatTyping"),
        },
    }

    def op(action: str, channel: str, names: list[str], summary: str) -> dict[str, Any]:
        return {
            "action": action,
            "channel": {"$ref": f"#/channels/{channel}"},
            "summary": summary,
            "messages": [{"$ref": f"#/channels/{channel}/messages/{n}"} for n in names],
        }

    operations = {
        "subscribe": op("send", "socket", ["Subscribe"], "Subscribe to a topic"),
        "unsubscribe": op("send", "socket", ["Unsubscribe"], "Unsubscribe from a topic"),
        "ping": op("send", "socket", ["Ping"], "Keep-alive"),
        "typing": op("send", "socket", ["Typing"], "Typing indicator in a chat"),
        "receiveControl": op(
            "receive",
            "socket",
            ["Subscribed", "Unsubscribed", "Snapshot", "Pong", "Heartbeat", "Error"],
            "Answers and connection messages",
        ),
        "receiveCandles": op("receive", "candles", ["Candle"], "Live candles"),
        "receiveSignals": op("receive", "signals", ["Signal"], "Live signals of an instrument"),
        "receiveUser": op(
            "receive",
            "user",
            [
                "UserSignal",
                "Notification",
                "BacktestProgress",
                "BacktestCompleted",
                "BacktestFailed",
                "WorkspaceUpdated",
                "PriceAlert",
            ],
            "Your own events",
        ),
        "receiveNews": op("receive", "news", ["News"], "New articles"),
        "receiveNewsInstrument": op(
            "receive", "newsInstrument", ["News"], "New articles of one instrument"
        ),
        "receiveChat": op(
            "receive",
            "chat",
            ["ChatMessage", "ChatMessageUpdated", "ChatRead", "ChatTyping"],
            "A conversation",
        ),
    }
    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "AI Trading Platform WebSocket",
            "version": "1.0.0",
            "description": (
                "Generated by backend/scripts/asyncapi.py; human guide: docs/websocket.md and "
                "docs/chat.md. Every server message carries type, and topic messages also "
                "topic and sent_at."
            ),
        },
        "servers": {
            "production": {
                "host": "187.127.76.76:8080",
                "protocol": "ws",
                "description": "The VPS (HTTP only until a domain exists)",
            },
            "local": {"host": "localhost", "protocol": "ws", "description": "docker compose"},
        },
        "defaultContentType": "application/json",
        "channels": channels,
        "operations": operations,
        "components": {"messages": messages, "schemas": DEFS},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if current == content:
        print("AsyncAPI document up to date")
        return 0
    if args.check:
        print(f"out of date: {OUT.relative_to(ROOT)}\nrun: python backend/scripts/asyncapi.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
