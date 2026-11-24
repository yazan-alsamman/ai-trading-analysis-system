"""The request sequences of the feed on one connection (protocol.py has the sources):
application auth, token refresh, account auth, the symbol, and M1 trend bars in chunks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.connection import Connection, CTraderError
from app.feeds.ctrader.credentials import Tokens

MINUTE = timedelta(minutes=1)
CHUNK = timedelta(days=1)  # 1,440 M1 bars per request, far below the ~14,000 bars reported


@dataclass(frozen=True)
class Symbol:
    symbol_id: int
    name: str
    digits: int


async def authorize_app(conn: Connection, client_id: str, client_secret: str) -> None:
    await conn.request(p.application_auth(client_id, client_secret))


async def refresh(conn: Connection, refresh_token: str) -> Tokens:
    """``ProtoOARefreshTokenReq``: a new access token **and a new refresh token** (the old pair
    is invalid from now on: persist the answer before anything else)."""
    _, payload = await conn.request(p.refresh_token(refresh_token))
    return Tokens.from_answer(payload)


async def authorize_account(conn: Connection, account_id: int, access_token: str) -> None:
    await conn.request(p.account_auth(account_id, access_token))


async def find_symbol(conn: Connection, account_id: int, name: str) -> Symbol:
    """The symbol by name (``ProtoOASymbolsListReq``), then its ``digits``
    (``ProtoOASymbolByIdReq``: only the full ``ProtoOASymbol`` has them)."""
    _, listing = await conn.request(p.symbols_list(account_id))
    wanted = name.replace("/", "").upper()
    found = [
        s
        for s in listing.get("symbol") or []
        if str(s.get("symbolName", "")).replace("/", "").upper() == wanted
    ]
    if not found:
        raise CTraderError("SYMBOL_NOT_FOUND", f"{name} is not in the account's symbols")
    symbol_id = int(found[0]["symbolId"])
    _, detail = await conn.request(p.symbol_by_id(account_id, symbol_id))
    [full] = detail.get("symbol") or [{}]
    return Symbol(symbol_id, str(found[0].get("symbolName", name)), int(full["digits"]))


async def fetch_m1(
    conn: Connection,
    account_id: int,
    symbol: Symbol,
    start: datetime,
    end: datetime,
    *,
    pause: float = 1 / p.HISTORY_REQUESTS_PER_SECOND,
) -> list[p.Trendbar]:
    """Closed M1 bars with ``start <= ts`` and ``ts + 1 min <= end``, oldest first, in 1-day
    chunks (a ``hasMore`` answer is completed with more requests), at most 4 history requests
    a second (the documented limit is 5)."""
    bars: dict[datetime, p.Trendbar] = {}
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + CHUNK, end)
        # hasMore: the answer was cut to its chunk size ("count ... back from toTimestamp"),
        # so ask again for whatever part of the range it did not cover, on either side
        pending = [(chunk_start, chunk_end)]
        while pending:
            a, b = pending.pop()
            _, payload = await conn.request(
                p.trendbars(account_id, symbol.symbol_id, _ms(a), _ms(b) - 1)
            )
            got = [p.trendbar(raw, symbol.digits) for raw in payload.get("trendbar") or []]
            for bar in got:
                if start <= bar.ts and bar.ts + MINUTE <= end:
                    bars[bar.ts] = bar
            await asyncio.sleep(pause)
            if payload.get("hasMore") and got:
                low, high = min(x.ts for x in got), max(x.ts for x in got) + MINUTE
                if low > a:
                    pending.append((a, low))
                if high < b:
                    pending.append((high, b))
        chunk_start = chunk_end
    return [bars[ts] for ts in sorted(bars)]


def _ms(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp() * 1000)
