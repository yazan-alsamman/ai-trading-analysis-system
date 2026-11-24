"""Admin: the cTrader live feed (B1, docs/ctrader-feed.md). Status, linking the account (OAuth),
choosing the account, and a long backfill. Tokens are never returned."""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, Field

from app.api.deps import AdminUser, SessionDep
from app.core.config import get_settings
from app.core.redis import get_redis
from app.feeds.ctrader import backfill, credentials, linking
from app.feeds.ctrader import store as feed_store
from app.feeds.ctrader.backfill import BackfillError
from app.feeds.ctrader.linking import LinkError

router = APIRouter(prefix="/admin/feeds/ctrader", tags=["admin"])
# cTrader's redirect lands here from the admin's browser, without our JWT: the one-time
# ``state`` issued by /connect is what authorises it
callback_router = APIRouter(prefix="/admin/feeds/ctrader", tags=["admin"])


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=128)


class AccountIn(BaseModel):
    account_id: int = Field(gt=0)


class BackfillIn(BaseModel):
    from_: AwareDatetime = Field(alias="from")
    to: AwareDatetime


def _raise(exc: Exception) -> None:
    code = exc.status if isinstance(exc, LinkError) else status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(code, str(exc)) from None


async def feed_status(session) -> dict[str, Any]:
    """The feed's status for admins (also in /admin/system/status): settings, the link (never
    the tokens), what the running service reports, the last manual backfill."""
    settings = get_settings()
    row = await credentials.load(session)
    redis = get_redis()
    live = await feed_store.read_status(redis)
    raw = await redis.get(backfill.STATUS_KEY)
    return {
        "enabled": settings.ctrader_enabled,
        "env": settings.ctrader_env,
        "symbol": settings.ctrader_symbol,
        "instrument": settings.ctrader_instrument,
        "app_credentials": bool(settings.ctrader_client_id and settings.ctrader_client_secret),
        "redirect_uri": credentials.redirect_uri(),
        "linked": row is not None,
        "link": None
        if row is None
        else {
            "env": row.env,
            "account_id": settings.ctrader_account_id or row.account_id,
            "accounts": row.accounts,
            "scope": row.scope,
            "linked_at": row.linked_at,
            "refreshed_at": row.refreshed_at,
            "token_expires_at": row.expires_at,
        },
        "state": live.get("state"),
        "connected": bool(live.get("connected")),
        "last_tick_at": live.get("last_tick_at"),
        "last_bar": live.get("last_bar"),
        "reconnects_24h": live.get("reconnects_24h", 0),
        "last_error": live.get("last_error"),
        "updated_at": live.get("updated_at"),
        "backfill": json.loads(raw) if raw else None,
    }


@router.get("")
async def ctrader_status(_: AdminUser, session: SessionDep) -> dict:
    """Enabled, linked (account, environment, token expiry), connected, the last tick and bar,
    reconnects in 24 h, the last error and the last manual backfill. Never the tokens."""
    return await feed_status(session)


@router.get("/connect")
async def ctrader_connect(admin: AdminUser) -> dict:
    """The cTrader authorization URL to open (scope ``accounts``: view only) with a one-time
    ``state`` valid 10 minutes, and the redirect URI it returns to (register it in the cTrader
    app first). 409 when the app credentials are not set on the server."""
    try:
        return await linking.start(get_redis(), admin.id)
    except LinkError as exc:
        _raise(exc)


@callback_router.get("/callback")
async def ctrader_callback(
    session: SessionDep,
    code: Annotated[str, Query(max_length=2048)] = "",
    state: Annotated[str | None, Query(max_length=128)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    """Where cTrader sends the admin back with ``?code=``: the state must be one /connect issued
    (see docs/ctrader-feed.md for a callback without state). Exchanges the code, stores the
    tokens encrypted, lists the accounts and chooses one when it can."""
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"cTrader answered: {error}")
    try:
        return await linking.finish(session, get_redis(), code, state)
    except LinkError as exc:
        _raise(exc)


@router.post("/code")
async def ctrader_code(data: CodeIn, _: AdminUser, session: SessionDep) -> dict:
    """The same as the callback, for a code pasted by hand (when the redirect cannot reach the
    server, or came back without state). The code lives one minute."""
    try:
        return await linking.finish(session, get_redis(), data.code, data.state)
    except LinkError as exc:
        _raise(exc)


@router.patch("")
async def ctrader_choose_account(data: AccountIn, _: AdminUser, session: SessionDep) -> dict:
    """Choose the trader account to stream (one of the linked token's accounts). Restart
    feed-ctrader afterwards. CTRADER_ACCOUNT_ID, when set, wins."""
    try:
        return await linking.choose(session, data.account_id)
    except LinkError as exc:
        _raise(exc)


@router.post("/backfill", status_code=status.HTTP_202_ACCEPTED)
async def ctrader_backfill(data: BackfillIn, _: AdminUser) -> dict:
    """Backfill M1 bars for ``[from, to]`` (at most 400 days) as a background task, a day per
    request; a bar built live (with a spread) is never overwritten. Its progress is in the
    status (``backfill``)."""
    try:
        backfill.check_range(data.from_, data.to)
    except BackfillError as exc:
        _raise(exc)
    from app.tasks import celery_app  # noqa: PLC0415

    start, end = data.from_.astimezone(UTC), min(data.to.astimezone(UTC), datetime.now(UTC))
    result = celery_app.send_task("feeds.ctrader_backfill", (start.isoformat(), end.isoformat()))
    days = (end - start) / timedelta(days=1)
    return {"task_id": result.id, "from": start, "to": end, "days": round(days, 2)}
