"""A mock cTrader Open API (JSON over WebSocket) for development and CI (B1). **Never in
production**: not in infra/deploy/docker-compose.prod.yml.

It speaks the messages app/feeds/ctrader implements, with the same payload types and fields
(app/feeds/ctrader/protocol.py cites the official sources):

- application auth (2100 -> 2101; a wrong client gives ``CH_CLIENT_AUTH_FAILURE``), accounts by
  token (2149 -> 2150), account auth (2102 -> 2103; an expired or unknown token gives
  ``CH_ACCESS_TOKEN_INVALID``), token refresh (2173 -> 2174; the refresh token rotates);
- the symbols list (2114 -> 2115) and the symbol by id (2116 -> 2117, ``digits``);
- spot subscription (2127 -> 2128), then spot events (2131) at ``tick_rate`` a second with
  ``bid``/``ask`` in 1/100000 of a price and the ``timestamp`` in ms; none while the market is
  closed (Friday 21:00 to Sunday 22:00 UTC, or ``weekend = True``);
- M1 trend bars (2137 -> 2138), ``low`` + deltas in 1/100000, at most ``max_bars`` per answer
  counted back from ``toTimestamp`` with ``hasMore``;
- heartbeats (51) every ``heartbeat_seconds``; a version request (2104 -> 2105);
- faults: ``expire_tokens()`` (refuses the access token and sends a token-invalidated event,
  2147), ``drop()`` (closes every connection).

The OAuth token endpoint (HTTP) is ``token_transport()``: an httpx transport for the tests.

Run it: ``python tools/fake_ctrader/fake_ctrader.py --port 5036`` (or the ``fake-ctrader``
service of docker-compose.yml, profile ``fake-ctrader``), then ``CTRADER_WS_URL=ws://...``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import secrets
import time
from datetime import UTC, datetime
from typing import Any

import websockets

SCALE = 100_000
# the frames carry the fake tokens and secret: never logged, even at DEBUG
_WIRE = logging.getLogger("fake_ctrader.wire")
_WIRE.setLevel(logging.WARNING)
CLIENT_ID, CLIENT_SECRET = "fake-client", "fake-secret"
ACCOUNT_ID, LIVE_ACCOUNT_ID = 1234567, 7654321
SYMBOLS = [
    {"symbolId": 1, "symbolName": "EURUSD", "enabled": True},
    {"symbolId": 41, "symbolName": "XAUUSD", "enabled": True},
]
DIGITS = {1: 5, 41: 2}


def bid_at(ts: float) -> float:
    """A deterministic XAU/USD-like bid at unix time ``ts``."""
    return round(2400 + 3 * math.sin(ts / 600) + 0.5 * math.sin(ts / 37), 2)


def spread_at(ts: float) -> float:
    return round(0.25 + 0.1 * math.sin(ts / 90), 2)


def market_closed(ts: float) -> bool:
    """Weekly close: Friday 21:00 UTC to Sunday 22:00 UTC."""
    t = datetime.fromtimestamp(ts, UTC)
    minutes = t.weekday() * 1440 + t.hour * 60 + t.minute  # Monday 00:00 = 0
    return 4 * 1440 + 21 * 60 <= minutes < 6 * 1440 + 22 * 60


class FakeCTrader:
    def __init__(
        self,
        *,
        tick_rate: float = 2.0,
        heartbeat_seconds: float = 10.0,
        max_bars: int = 1000,
        clock=time.time,
    ) -> None:
        self.clock = clock  # the market's time (tests run it faster than real time)
        self.tick_rate = tick_rate
        self.heartbeat_seconds = heartbeat_seconds
        self.max_bars = max_bars
        self.weekend = False
        self.always_open = (
            False  # ignore the weekly close (e.g. a load test on a Saturday)
        )
        self.access_tokens: dict[str, float] = {}  # token -> expiry (unix)
        self.refresh_tokens: set[str] = set()
        self.codes: set[str] = set()
        self.received: list[int] = []  # payload types, in order
        self.connections: set[Any] = set()
        self.subscriptions: dict[Any, tuple[int, int]] = {}  # ws -> (account, symbol)
        self.server: Any = None
        self.port = 0

    # --- tokens ----------------------------------------------------------------------------------

    def issue(self, lifetime: float = 2_628_000) -> dict[str, Any]:
        access, refresh = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        self.access_tokens[access] = self.clock() + lifetime
        self.refresh_tokens.add(refresh)
        return {
            "accessToken": access,
            "tokenType": "bearer",
            "expiresIn": int(lifetime),
            "refreshToken": refresh,
            "errorCode": None,
            "description": None,
        }

    def new_code(self) -> str:
        code = secrets.token_urlsafe(8)
        self.codes.add(code)
        return code

    def expire_tokens(self) -> None:
        """Every access token stops working; connected clients get the invalidated event."""
        self.access_tokens = {t: 0.0 for t in self.access_tokens}
        for ws in list(self.connections):
            asyncio.ensure_future(
                self._send(
                    ws,
                    2147,
                    {"ctidTraderAccountIds": [ACCOUNT_ID], "reason": "expired"},
                )
            )

    def token_valid(self, token: str) -> bool:
        return self.access_tokens.get(token, 0) > self.clock()

    def token_transport(self):
        """The OAuth token endpoint (https://openapi.ctrader.com/apps/token) for httpx."""
        import httpx

        def handle(request: httpx.Request) -> httpx.Response:
            q = request.url.params
            if (
                q.get("client_id") != CLIENT_ID
                or q.get("client_secret") != CLIENT_SECRET
            ):
                return httpx.Response(200, json={"errorCode": "ACCESS_DENIED"})
            if (
                q.get("grant_type") == "authorization_code"
                and q.get("code") in self.codes
            ):
                self.codes.discard(q["code"])
                return httpx.Response(200, json=self.issue())
            if (
                q.get("grant_type") == "refresh_token"
                and q.get("refresh_token") in self.refresh_tokens
            ):
                self.refresh_tokens.discard(q["refresh_token"])
                return httpx.Response(200, json=self.issue())
            return httpx.Response(200, json={"errorCode": "INVALID_REQUEST"})

        return httpx.MockTransport(handle)

    # --- server ----------------------------------------------------------------------------------

    async def start(self, port: int = 0) -> str:
        self.server = await websockets.serve(
            self._serve, "127.0.0.1", port, logger=_WIRE
        )
        self.port = self.server.sockets[0].getsockname()[1]
        return f"ws://127.0.0.1:{self.port}"

    async def stop(self) -> None:
        self.drop()
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    def drop(self) -> None:
        """A dropped connection: every client is cut off."""
        for ws in list(self.connections):
            asyncio.ensure_future(ws.close(code=1011, reason="dropped"))

    async def _send(
        self, ws, payload_type: int, payload: dict, msg_id: str | None = None
    ) -> None:
        message = {"payloadType": payload_type, "payload": payload}
        if msg_id:
            message["clientMsgId"] = msg_id
        try:
            await ws.send(json.dumps(message))
        except websockets.ConnectionClosed:
            pass

    async def _serve(self, ws) -> None:
        self.connections.add(ws)
        state = {"app": False, "accounts": set()}
        tasks = [
            asyncio.create_task(self._heartbeats(ws)),
            asyncio.create_task(self._ticks(ws)),
        ]
        try:
            async for raw in ws:
                message = json.loads(raw)
                await self._handle(ws, state, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            for task in tasks:
                task.cancel()
            self.connections.discard(ws)
            self.subscriptions.pop(ws, None)

    async def _handle(self, ws, state: dict, message: dict) -> None:
        payload_type = int(message["payloadType"])
        payload = message.get("payload") or {}
        msg_id = message.get("clientMsgId")
        self.received.append(payload_type)

        async def answer(answer_type: int, body: dict) -> None:
            await self._send(ws, answer_type, body, msg_id)

        async def error(code: str, description: str = "") -> None:
            await answer(2142, {"errorCode": code, "description": description})

        if payload_type == 51:
            return
        if payload_type == 2100:
            if (
                payload.get("clientId") == CLIENT_ID
                and payload.get("clientSecret") == CLIENT_SECRET
            ):
                state["app"] = True
                return await answer(2101, {})
            return await error("CH_CLIENT_AUTH_FAILURE", "wrong client")
        if not state["app"]:
            return await error("CH_CLIENT_NOT_AUTHENTICATED")
        if payload_type == 2104:
            return await answer(2105, {"version": "fake"})
        if payload_type == 2149:
            if not self.token_valid(payload.get("accessToken", "")):
                return await error("CH_ACCESS_TOKEN_INVALID")
            accounts = [
                {"ctidTraderAccountId": ACCOUNT_ID, "isLive": False, "traderLogin": 1001,
                 "brokerTitleShort": "FxPro"},
                {"ctidTraderAccountId": LIVE_ACCOUNT_ID, "isLive": True, "traderLogin": 2002,
                 "brokerTitleShort": "FxPro"},
            ]  # fmt: skip
            return await answer(
                2150, {"accessToken": payload["accessToken"], "permissionScope": 0,
                       "ctidTraderAccount": accounts}
            )  # fmt: skip
        if payload_type == 2173:
            token = payload.get("refreshToken", "")
            if token not in self.refresh_tokens:
                return await error("CH_ACCESS_TOKEN_INVALID", "unknown refresh token")
            self.refresh_tokens.discard(token)
            issued = self.issue()
            return await answer(2174, {k: issued[k] for k in
                                       ("accessToken", "tokenType", "expiresIn", "refreshToken")})  # fmt: skip
        if payload_type == 2102:
            if not self.token_valid(payload.get("accessToken", "")):
                return await error(
                    "CH_ACCESS_TOKEN_INVALID", "Access token expired or invalid"
                )
            state["accounts"].add(int(payload["ctidTraderAccountId"]))
            return await answer(
                2103, {"ctidTraderAccountId": payload["ctidTraderAccountId"]}
            )
        account = int(payload.get("ctidTraderAccountId", 0))
        if account not in state["accounts"]:
            return await error("ACCOUNT_NOT_AUTHORIZED")
        if payload_type == 2114:
            return await answer(
                2115, {"ctidTraderAccountId": account, "symbol": SYMBOLS}
            )
        if payload_type == 2116:
            found = [
                {"symbolId": s, "digits": DIGITS[s], "pipPosition": DIGITS[s] - 1}
                for s in payload.get("symbolId", [])
                if s in DIGITS
            ]
            return await answer(2117, {"ctidTraderAccountId": account, "symbol": found})
        if payload_type == 2127:
            self.subscriptions[ws] = (account, int(payload["symbolId"][0]))
            return await answer(2128, {"ctidTraderAccountId": account})
        if payload_type == 2137:
            return await answer(2138, self._trendbars(account, payload))
        return await error("UNSUPPORTED_MESSAGE")

    def _trendbars(self, account: int, payload: dict) -> dict:
        start = int(payload["fromTimestamp"]) // 60_000
        end = int(payload["toTimestamp"]) // 60_000  # inclusive minute of toTimestamp
        now = int(self.clock()) // 60
        # bars of closed minutes only (the forming one is not a bar yet)
        minutes = [
            m for m in range(start, min(end, now - 1) + 1) if not market_closed(m * 60)
        ]
        has_more = len(minutes) > self.max_bars
        minutes = minutes[-self.max_bars :]  # "count ... back from toTimestamp"
        bars = []
        for m in minutes:
            prices = [bid_at(m * 60 + s) for s in range(0, 60, 5)]
            low = round(min(prices) * SCALE)
            bars.append(
                {
                    "volume": 12,
                    "period": "M1",
                    "low": low,
                    "deltaOpen": round(prices[0] * SCALE) - low,
                    "deltaHigh": round(max(prices) * SCALE) - low,
                    "deltaClose": round(prices[-1] * SCALE) - low,
                    "utcTimestampInMinutes": m,
                }
            )
        return {
            "ctidTraderAccountId": account,
            "period": payload.get("period", 1),
            "trendbar": bars,
            "symbolId": payload["symbolId"],
            "hasMore": has_more,
        }

    async def _heartbeats(self, ws) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self._send(ws, 51, {})

    async def _ticks(self, ws) -> None:
        while True:
            await asyncio.sleep(1 / self.tick_rate if self.tick_rate > 0 else 1)
            sub = self.subscriptions.get(ws)
            now = self.clock()
            closed = market_closed(now) and not self.always_open
            if sub is None or self.tick_rate <= 0 or self.weekend or closed:
                continue
            bid = bid_at(now)
            ask = round(bid + spread_at(now), 2)
            await self._send(
                ws,
                2131,
                {
                    "ctidTraderAccountId": sub[0],
                    "symbolId": sub[1],
                    "bid": round(bid * SCALE),
                    "ask": round(ask * SCALE),
                    "timestamp": int(now * 1000),
                },
            )


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="mock cTrader Open API (JSON over WebSocket)"
    )
    parser.add_argument("--port", type=int, default=5036)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--tick-rate", type=float, default=2.0)
    parser.add_argument(
        "--always-open", action="store_true", help="ticks on weekends too"
    )
    args = parser.parse_args()
    fake = FakeCTrader(tick_rate=args.tick_rate)
    fake.always_open = args.always_open
    fake.server = await websockets.serve(
        fake._serve, args.host, args.port, logger=_WIRE
    )
    token = fake.issue()
    print(f"fake cTrader on ws://{args.host}:{args.port}; a valid access token: "
          f"{token['accessToken']}", flush=True)  # fmt: skip
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_main())
