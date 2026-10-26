"""cTrader OAuth tokens and the linked account (B1, docs/ctrader-feed.md#tokens).

OAuth (https://help.ctrader.com/open-api/account-authentication/):

- The admin opens ``AUTH_URL?client_id=..&redirect_uri=..&scope=accounts&product=web``
  (``accounts`` = "View only access": enough to read prices and trend bars; ``trading`` would
  also allow trading, which this feed never needs).
- cTrader redirects to the registered redirect URI with ``?code=``; the code lives one minute.
- ``TOKEN_URL`` with ``grant_type=authorization_code`` gives ``accessToken``, ``refreshToken``,
  ``expiresIn`` (default 2,628,000 s, about 30 days) and ``tokenType``; ``errorCode`` and
  ``description`` are null on success. The refresh token does not expire but **changes on every
  refresh** (the old pair is invalidated), so the tokens live in the database, encrypted
  (``app/feeds/secrets.py``), never in ``.env``.

Nothing here logs a token, a code or the client secret.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.feeds import secrets as box
from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.connection import Connection
from app.models.feed import FeedCredential

logger = logging.getLogger(__name__)

PROVIDER = "ctrader"
SCOPE = "accounts"  # view only: prices and trend bars; no trading permission is asked for
AUTH_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"
CALLBACK_PATH = "/api/v1/admin/feeds/ctrader/callback"
FALLBACK_BASE_URL = "http://187.127.76.76:8080"
REFRESH_BEFORE = timedelta(days=7)  # refresh when less is left (tokens last ~30 days)
HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests: the fake token endpoint


class OAuthError(Exception):
    """The token endpoint refused (its errorCode; never the secret or the code)."""


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: datetime

    @classmethod
    def from_answer(cls, data: dict[str, Any], now: datetime | None = None) -> Tokens:
        now = now or datetime.now(UTC)
        return cls(
            access_token=str(data["accessToken"]),
            refresh_token=str(data["refreshToken"]),
            expires_at=now + timedelta(seconds=int(data.get("expiresIn") or 2_628_000)),
        )

    def __repr__(self) -> str:  # never the tokens themselves
        return f"Tokens(expires_at={self.expires_at.isoformat()})"


def redirect_uri() -> str:
    """The URI to register in the cTrader app: PUBLIC_BASE_URL (or the server's IP:8080) plus
    the callback path."""
    base = get_settings().public_base_url.rstrip("/") or FALLBACK_BASE_URL
    return base + CALLBACK_PATH


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    query = {
        "client_id": get_settings().ctrader_client_id,
        "redirect_uri": redirect_uri(),
        "scope": SCOPE,
        "product": "web",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(query)}"


async def exchange_code(code: str, *, transport: httpx.AsyncBaseTransport | None = None) -> Tokens:
    """The authorization code for tokens (``grant_type=authorization_code``)."""
    settings = get_settings()
    params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": settings.ctrader_client_id,
        "client_secret": settings.ctrader_client_secret,
    }
    async with httpx.AsyncClient(transport=transport or HTTP_TRANSPORT, timeout=20) as http:
        response = await http.get(TOKEN_URL, params=params)
    try:
        data = response.json()
    except ValueError:
        raise OAuthError(f"token endpoint answered HTTP {response.status_code}") from None
    if response.status_code != 200 or data.get("errorCode") or not data.get("accessToken"):
        raise OAuthError(str(data.get("errorCode") or f"HTTP {response.status_code}"))
    return Tokens.from_answer(data)


async def list_accounts(access_token: str, url: str | None = None) -> list[dict[str, Any]]:
    """The trader accounts the token can see (``ProtoOAGetAccountListByAccessTokenReq``), on
    the host of CTRADER_ENV."""
    settings = get_settings()
    async with Connection(url or p.ws_url(settings.ctrader_env, settings.ctrader_ws_url)) as conn:
        await conn.request(
            p.application_auth(settings.ctrader_client_id, settings.ctrader_client_secret)
        )
        _, payload = await conn.request(p.accounts_by_token(access_token))
    return [
        {
            "account_id": int(a["ctidTraderAccountId"]),
            "is_live": bool(a.get("isLive", False)),
            "trader_login": a.get("traderLogin"),
            "broker": a.get("brokerTitleShort"),
        }
        for a in payload.get("ctidTraderAccount") or []
    ]


async def load(session: AsyncSession) -> FeedCredential | None:
    return await session.get(FeedCredential, PROVIDER, populate_existing=True)


def tokens_of(row: FeedCredential) -> Tokens:
    return Tokens(
        box.decrypt(row.access_token_enc), box.decrypt(row.refresh_token_enc), row.expires_at
    )


async def save_link(
    session: AsyncSession,
    tokens: Tokens,
    accounts: list[dict[str, Any]],
    account_id: int | None,
) -> FeedCredential:
    """Store a new link (replacing an older one): the tokens, encrypted, and the accounts."""
    now = datetime.now(UTC)
    values = {
        "env": get_settings().ctrader_env,
        "access_token_enc": box.encrypt(tokens.access_token),
        "refresh_token_enc": box.encrypt(tokens.refresh_token),
        "expires_at": tokens.expires_at,
        "scope": SCOPE,
        "account_id": account_id,
        "accounts": accounts,
        "linked_at": now,
        "refreshed_at": None,
        "updated_at": now,
    }
    await session.execute(
        insert(FeedCredential)
        .values(provider=PROVIDER, **values)
        .on_conflict_do_update(index_elements=["provider"], set_=values)
    )
    await session.commit()
    row = await load(session)
    assert row is not None
    return row


async def save_refreshed(session: AsyncSession, tokens: Tokens) -> None:
    """Persist a refreshed pair at once: the old refresh token is invalid from now on."""
    row = await load(session)
    if row is None:
        return
    row.access_token_enc = box.encrypt(tokens.access_token)
    row.refresh_token_enc = box.encrypt(tokens.refresh_token)
    row.expires_at = tokens.expires_at
    row.refreshed_at = datetime.now(UTC)
    await session.commit()


def choose_account(accounts: list[dict[str, Any]], env: str) -> int | None:
    """The account to use without asking: CTRADER_ACCOUNT_ID when set, else the only account
    of the configured environment (None: the admin picks one with PATCH)."""
    configured = get_settings().ctrader_account_id
    if configured is not None:
        return configured
    matching = [a for a in accounts if a["is_live"] == (env == "live")]
    return matching[0]["account_id"] if len(matching) == 1 else None


def needs_refresh(tokens: Tokens, now: datetime | None = None) -> bool:
    return tokens.expires_at - (now or datetime.now(UTC)) < REFRESH_BEFORE
