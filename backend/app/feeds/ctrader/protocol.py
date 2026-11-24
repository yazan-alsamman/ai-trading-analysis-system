"""cTrader Open API, JSON over WebSocket: the messages this feed uses (B1, docs/ctrader-feed.md).

Every number and field name below is copied from the official sources, not from memory:

- Payload types and fields: ``spotware/openapi-proto-messages`` (commit 3fd8bddf, files
  ``OpenApiModelMessages.proto`` enum ``ProtoOAPayloadType``, ``OpenApiMessages.proto``,
  ``OpenApiCommonModelMessages.proto`` enum ``ProtoPayloadType``),
  https://github.com/spotware/openapi-proto-messages
- JSON envelope ``{"clientMsgId", "payloadType", "payload"}`` and port 5036 for JSON:
  https://help.ctrader.com/open-api/protocol-buffers-json/ and
  https://help.ctrader.com/open-api/sending-receiving-json/
- Hosts: ``demo.ctraderapi.com:5036`` / ``live.ctraderapi.com:5036``; demo and live are fully
  separated (an account only works on its own host): https://help.ctrader.com/open-api/proxies-endpoints/
- Rate limits: 50 requests/s, **5 requests/s for historical data**, per connection:
  https://help.ctrader.com/open-api/
- Prices: ``ProtoOASpotEvent.bid/ask`` are "Specified in 1/100000 of unit of a price. (e.g.
  123000 in protocol means 1.23, 53423782 means 534.23782)" (OpenApiMessages.proto). Trend
  bars: ``low`` plus ``deltaOpen/deltaHigh/deltaClose``, divided by 100000, with the open time
  ``utcTimestampInMinutes * 60`` (the official sample ``spotware/OpenApiPy``
  ``samples/jupyter/main.ipynb``). The scale is fixed: ``digits`` only says how many decimals
  to keep.
- Heartbeat: ``ProtoHeartbeatEvent`` (51) "can be used as criteria that connection is healthy
  ... client can send this message when he needs to keep the connection open for a period
  without other messages longer than 30 seconds" (OpenApiCommonMessages.proto).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# --- payload types (ProtoPayloadType / ProtoOAPayloadType) ---------------------------------------
ERROR_RES = 50
HEARTBEAT_EVENT = 51
APPLICATION_AUTH_REQ = 2100
APPLICATION_AUTH_RES = 2101
ACCOUNT_AUTH_REQ = 2102
ACCOUNT_AUTH_RES = 2103
SYMBOLS_LIST_REQ = 2114
SYMBOLS_LIST_RES = 2115
SYMBOL_BY_ID_REQ = 2116
SYMBOL_BY_ID_RES = 2117
SUBSCRIBE_SPOTS_REQ = 2127
SUBSCRIBE_SPOTS_RES = 2128
SPOT_EVENT = 2131
GET_TRENDBARS_REQ = 2137
GET_TRENDBARS_RES = 2138
OA_ERROR_RES = 2142
ACCOUNTS_TOKEN_INVALIDATED_EVENT = 2147
CLIENT_DISCONNECT_EVENT = 2148
GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
ACCOUNT_DISCONNECT_EVENT = 2164
REFRESH_TOKEN_REQ = 2173
REFRESH_TOKEN_RES = 2174

# ProtoOATrendbarPeriod
PERIOD_M1 = 1

# ProtoOAErrorCode values that mean "the access token is no good": refresh and re-authorise
TOKEN_ERRORS = frozenset(
    {"OA_AUTH_TOKEN_EXPIRED", "CH_ACCESS_TOKEN_INVALID", "ACCOUNT_NOT_AUTHORIZED"}
)

PRICE_SCALE = 100_000  # 1/100000 of a unit of price (OpenApiMessages.proto, ProtoOASpotEvent)
HOSTS = {"demo": "wss://demo.ctraderapi.com:5036", "live": "wss://live.ctraderapi.com:5036"}
HEARTBEAT_SECONDS = 10.0  # we send one every 10 s (the server's limit is 30 s of silence)
HISTORY_REQUESTS_PER_SECOND = 4  # below the documented 5 per connection


def ws_url(env: str, override: str = "") -> str:
    return override or HOSTS[env]


def envelope(payload_type: int, payload: dict[str, Any], client_msg_id: str) -> dict[str, Any]:
    return {"clientMsgId": client_msg_id, "payloadType": payload_type, "payload": payload}


def price(raw: int | float, digits: int | None = None) -> float:
    """A protocol price (1/100000 of a unit) as a float, rounded to the symbol's ``digits``."""
    value = raw / PRICE_SCALE
    return round(value, digits) if digits is not None else value


@dataclass(frozen=True)
class Trendbar:
    """A decoded ``ProtoOATrendbar`` (prices in price units, ``ts`` = the bar's open, UTC)."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int  # "Bar volume in ticks."


def trendbar(raw: dict[str, Any], digits: int | None = None) -> Trendbar:
    """``low`` + ``deltaOpen/deltaHigh/deltaClose`` over 100000 (OpenApiPy sample); the deltas
    are optional in the proto (absent = 0)."""
    low = int(raw["low"])
    return Trendbar(
        ts=datetime.fromtimestamp(int(raw["utcTimestampInMinutes"]) * 60, UTC),
        open=price(low + int(raw.get("deltaOpen", 0)), digits),
        high=price(low + int(raw.get("deltaHigh", 0)), digits),
        low=price(low, digits),
        close=price(low + int(raw.get("deltaClose", 0)), digits),
        volume=int(raw.get("volume", 0)),
    )


# --- requests ------------------------------------------------------------------------------------


def application_auth(client_id: str, client_secret: str) -> tuple[int, dict]:
    return APPLICATION_AUTH_REQ, {"clientId": client_id, "clientSecret": client_secret}


def account_auth(account_id: int, access_token: str) -> tuple[int, dict]:
    return ACCOUNT_AUTH_REQ, {"ctidTraderAccountId": account_id, "accessToken": access_token}


def refresh_token(token: str) -> tuple[int, dict]:
    return REFRESH_TOKEN_REQ, {"refreshToken": token}


def accounts_by_token(access_token: str) -> tuple[int, dict]:
    return GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": access_token}


def symbols_list(account_id: int) -> tuple[int, dict]:
    return SYMBOLS_LIST_REQ, {"ctidTraderAccountId": account_id}


def symbol_by_id(account_id: int, symbol_id: int) -> tuple[int, dict]:
    return SYMBOL_BY_ID_REQ, {"ctidTraderAccountId": account_id, "symbolId": [symbol_id]}


def subscribe_spots(account_id: int, symbol_id: int) -> tuple[int, dict]:
    # subscribeToSpotTimestamp: the spot events then carry the server's timestamp (ms)
    return SUBSCRIBE_SPOTS_REQ, {
        "ctidTraderAccountId": account_id,
        "symbolId": [symbol_id],
        "subscribeToSpotTimestamp": True,
    }


def trendbars(account_id: int, symbol_id: int, start_ms: int, end_ms: int) -> tuple[int, dict]:
    return GET_TRENDBARS_REQ, {
        "ctidTraderAccountId": account_id,
        "symbolId": symbol_id,
        "period": PERIOD_M1,
        "fromTimestamp": start_ms,
        "toTimestamp": end_ms,
    }


def heartbeat() -> tuple[int, dict]:
    return HEARTBEAT_EVENT, {}
