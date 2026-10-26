"""Linking the cTrader account (admin, once; docs/ctrader-feed.md#linking).

1. ``start``: a random ``state`` kept 10 minutes in Redis with the admin who asked, and the
   cTrader authorization URL (scope ``accounts``: view only).
2. ``finish(code, state)``: the state must be one ``start`` issued (CSRF: a code that arrives
   with another state is refused); the code is exchanged for tokens, the accounts the token
   sees are listed, the tokens are stored encrypted with the accounts and the chosen account
   (CTRADER_ACCOUNT_ID, or the only account of CTRADER_ENV; otherwise the admin picks one).

cTrader's documentation does not say that it sends ``state`` back to the redirect URI. When the
callback comes **without** a state, it is accepted only if exactly one link was started in the
last 10 minutes (that one is consumed); otherwise the admin pastes the code into
``POST /admin/feeds/ctrader/code`` with the state of the connect answer.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.feeds.ctrader import credentials

logger = logging.getLogger(__name__)

STATE_KEY = "feeds:ctrader:oauth:"  # + state -> {"admin_id"}
STATE_TTL = 600


class LinkError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


async def start(redis: Redis, admin_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ctrader_client_id or not settings.ctrader_client_secret:
        raise LinkError(409, "CTRADER_CLIENT_ID / CTRADER_CLIENT_SECRET are not set on the server")
    state = credentials.new_state()
    await redis.set(STATE_KEY + state, json.dumps({"admin_id": str(admin_id)}), ex=STATE_TTL)
    return {
        "url": credentials.authorize_url(state),
        "redirect_uri": credentials.redirect_uri(),
        "scope": credentials.SCOPE,
        "state": state,
        "expires_in": STATE_TTL,
        "env": settings.ctrader_env,
    }


async def _consume_state(redis: Redis, state: str | None) -> None:
    if state:
        if not await redis.getdel(STATE_KEY + state):
            raise LinkError(400, "unknown or expired state: start again with /connect")
        return
    pending = [key async for key in redis.scan_iter(match=STATE_KEY + "*")]
    if len(pending) != 1:
        raise LinkError(
            400,
            "the callback came without state and it is not clear which link it answers: "
            "paste the code into POST /api/v1/admin/feeds/ctrader/code with the state",
        )
    await redis.delete(pending[0])


async def finish(
    session: AsyncSession, redis: Redis, code: str, state: str | None
) -> dict[str, Any]:
    if not code:
        raise LinkError(400, "no authorization code")
    await _consume_state(redis, state)
    try:
        tokens = await credentials.exchange_code(code)
    except credentials.OAuthError as exc:
        raise LinkError(502, f"cTrader refused the code: {exc}") from None
    try:
        accounts = await credentials.list_accounts(tokens.access_token)
    except Exception as exc:  # noqa: BLE001 - the link is kept; the account is picked later
        logger.warning("cTrader: listing the accounts failed: %s", type(exc).__name__)
        accounts = []
    env = get_settings().ctrader_env
    account_id = credentials.choose_account(accounts, env)
    row = await credentials.save_link(session, tokens, accounts, account_id)
    logger.info("cTrader account linked (%d accounts, chosen %s)", len(accounts), account_id)
    return {
        "linked": True,
        "env": row.env,
        "account_id": row.account_id,
        "accounts": accounts,
        "token_expires_at": row.expires_at,
        "next": (
            "set CTRADER_ENABLED=true and restart feed-ctrader"
            if account_id is not None
            else "pick the account with PATCH /api/v1/admin/feeds/ctrader {account_id}"
        ),
    }


async def choose(session: AsyncSession, account_id: int) -> dict[str, Any]:
    row = await credentials.load(session)
    if row is None:
        raise LinkError(409, "no cTrader account is linked: GET /admin/feeds/ctrader/connect")
    known = {a["account_id"] for a in row.accounts or []}
    if known and account_id not in known:
        raise LinkError(422, f"account {account_id} is not one the token can see: {sorted(known)}")
    row.account_id = account_id
    await session.commit()
    return {"account_id": account_id}
