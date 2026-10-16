"""Workspaces: saved trading screens, edited from several devices.

- Structural changes of one user's workspaces (create, delete, reorder, default switch, the
  default created on first read) take a per-user advisory transaction lock, so limits,
  positions and the single default stay consistent when two devices act at once.
- State changes are optimistic: ``UPDATE ... WHERE id AND version = :v RETURNING`` bumps the
  version atomically; a stale version gets 409 with the current one (:class:`VersionConflict`).
- Every successful change is announced on the owner's ``user:{id}`` topic
  (``workspace_updated``); publish failures are logged, never raised.
"""

import json
import logging
import secrets
import uuid
from collections.abc import Iterable
from typing import Any

import trading_strategies as ts
from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.custom_strategy import KEY_PREFIX as CUSTOM_PREFIX
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.instrument import Instrument
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.realtime import publisher
from app.realtime.topics import user_topic
from app.schemas.workspaces import (
    MAX_STATE_BYTES,
    SCHEMA_VERSION,
    Loc,
    SharedImport,
    Template,
    WorkspaceCreate,
    WorkspaceState,
    WorkspaceUpdate,
    error,
    state_errors,
)
from app.services import market_service, strategy_resolver

logger = logging.getLogger(__name__)

DEFAULT_NAME = "Main"
SHARE_ROLES = frozenset({UserRole.analyst, UserRole.expert, UserRole.admin})

CREATED = "created"
STATE_UPDATED = "state_updated"
RENAMED = "renamed"
DEFAULT_CHANGED = "default_changed"
DELETED = "deleted"
REORDERED = "reordered"
SHARED = "shared"
UNSHARED = "unshared"


class VersionConflict(Exception):
    """409 with the current version (handler in app.main), so the client can reload."""

    def __init__(self, workspace: Workspace) -> None:
        super().__init__("Workspace was changed by another client")
        self.current_version = workspace.version
        self.updated_at = workspace.updated_at

    def body(self) -> dict[str, Any]:
        return {
            "detail": "Workspace was changed by another client; reload it and apply your change "
            "again",
            "current_version": self.current_version,
            "updated_at": self.updated_at.isoformat(),
        }


# --- helpers ---------------------------------------------------------------------------------


async def _lock_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialize structural changes of one user's workspaces until the transaction ends."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"workspaces:{user_id}"},
    )


async def publish(user_id: uuid.UUID, workspace_id: uuid.UUID | None, version, action: str):
    """``workspace_updated`` on the owner's topic; never raises."""
    payload = {
        "type": "workspace_updated",
        "workspace_id": str(workspace_id) if workspace_id else None,
        "version": version,
        "action": action,
    }
    try:
        await publisher.publish(user_topic(user_id), payload)
    except Exception:  # noqa: BLE001 - the change is committed; a Redis outage must not fail it
        logger.exception("Publishing workspace_updated (%s) for user %s failed", action, user_id)


def parse_if_match(value: str | None) -> int | None:
    """``If-Match: "3"`` / ``W/"3"`` / ``3`` -> 3; absent or ``*`` -> None."""
    if value is None or value.strip() == "*":
        return None
    raw = value.strip().removeprefix("W/").strip('"')
    try:
        version = int(raw)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, 'If-Match must be a version, e.g. "3"'
        ) from None
    if version < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "If-Match must be >= 1")
    return version


def pick_version(body_version: int | None, if_match: str | None) -> int | None:
    header = parse_if_match(if_match)
    if body_version is not None and header is not None and body_version != header:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "version and If-Match disagree")
    return body_version if body_version is not None else header


def _limit(user: User) -> int:
    return get_settings().workspace_limit(user.role.value)


async def _count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count()).select_from(Workspace).where(Workspace.user_id == user_id)
    )


async def _name_taken(
    session: AsyncSession, user_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    query = select(Workspace.id).where(
        Workspace.user_id == user_id, func.lower(Workspace.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(Workspace.id != exclude)
    return (await session.scalar(query.limit(1))) is not None


async def _unique_name(session: AsyncSession, user_id: uuid.UUID, base: str) -> str:
    """``base``, else ``base (copy)``, ``base (copy 2)``, ... within 60 characters."""
    if not await _name_taken(session, user_id, base):
        return base
    for n in range(1, 1000):
        suffix = " (copy)" if n == 1 else f" (copy {n})"
        candidate = base[: 60 - len(suffix)].rstrip() + suffix
        if not await _name_taken(session, user_id, candidate):
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, "Could not find a free workspace name")


def _duplicate_name() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "You already have a workspace with this name")


async def _next_position(session: AsyncSession, user_id: uuid.UUID) -> int:
    current = await session.scalar(
        select(func.max(Workspace.position)).where(Workspace.user_id == user_id)
    )
    return 0 if current is None else current + 1


async def _commit_or_conflict(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "uq_workspaces_user_name" in str(exc.orig):
            raise _duplicate_name() from None
        raise


# --- validation ------------------------------------------------------------------------------


def _instrument_refs(state: dict[str, Any] | WorkspaceState) -> list[tuple[Loc, uuid.UUID]]:
    if isinstance(state, WorkspaceState):
        panels = [(p, panel.instrument_id) for p, panel in enumerate(state.panels)]
        watchlist = list(state.watchlist)
    else:
        panels = [(p, panel.get("instrument_id")) for p, panel in enumerate(state["panels"])]
        watchlist = state.get("watchlist", [])
    refs: list[tuple[Loc, uuid.UUID]] = [
        (("panels", p, "instrument_id"), uuid.UUID(str(i))) for p, i in panels if i is not None
    ]
    refs += [(("watchlist", w), uuid.UUID(str(i))) for w, i in enumerate(watchlist)]
    return refs


async def _instruments(session: AsyncSession, ids: Iterable[uuid.UUID]) -> dict:
    ids = set(ids)
    if not ids:
        return {}
    rows = await session.scalars(select(Instrument).where(Instrument.id.in_(ids)))
    return {row.id: row for row in rows}


def _custom_keys(state: dict[str, Any] | WorkspaceState) -> set[str]:
    """``custom:<uuid>`` strategy overlays of a state (lower case)."""
    if isinstance(state, WorkspaceState):
        keys = [s.strategy_key for p in state.panels for s in p.strategies]
    else:
        keys = [s.get("strategy_key", "") for p in state["panels"] for s in p.get("strategies", [])]
    return {k.lower() for k in keys if k.lower().startswith(CUSTOM_PREFIX)}


async def _usable_custom(
    session: AsyncSession, keys: Iterable[str], user_id: uuid.UUID | None
) -> set[str]:
    """The custom keys ``user_id`` may use: their own strategies and public ones (only public
    ones without a user, e.g. a shared link)."""
    ids = {cid for key in keys if (cid := strategy_resolver.custom_id(key)) is not None}
    if not ids:
        return set()
    rows = await session.scalars(select(CustomStrategy).where(CustomStrategy.id.in_(ids)))
    return {
        r.key
        for r in rows
        if r.visibility == Visibility.public or (user_id is not None and r.user_id == user_id)
    }


async def validate_state(
    session: AsyncSession,
    state: WorkspaceState,
    *,
    keep: Iterable[uuid.UUID] = (),
    prefix: Loc = ("body", "state"),
    user: User | None = None,
    keep_custom: Iterable[str] = (),
) -> dict[str, Any]:
    """The document to store, or 422 with every error (``loc`` = JSON path).

    Instruments must exist; inactive ones are fine, and ids already in the stored state
    (``keep``) may stay even if the instrument was deleted, so a workspace never breaks.
    """
    usable = await _usable_custom(session, _custom_keys(state), user.id if user else None)
    errors = state_errors(state, prefix, custom_ok=usable | set(keep_custom))
    refs = _instrument_refs(state)
    known = await _instruments(session, (i for _, i in refs))
    allowed = set(known) | set(keep)
    for loc, instrument_id in refs:
        if instrument_id not in allowed:
            errors.append(error((*prefix, *loc), f"unknown instrument {instrument_id}"))
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, errors)
    stored = state.stored()
    size = len(json.dumps(stored, separators=(",", ":")).encode())
    if size > MAX_STATE_BYTES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [error(prefix, f"state is {size} bytes serialized, at most {MAX_STATE_BYTES}")],
        )
    return stored


# --- templates -------------------------------------------------------------------------------

CRYPTO_SEEDS = ("BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT")


async def _seeded(session: AsyncSession, symbols: Iterable[str]) -> dict[str, uuid.UUID | None]:
    out = {}
    for symbol in symbols:
        row = await market_service.get_instrument_by_symbol(session, "binance", symbol)
        out[symbol] = row.id if row is not None else None
    return out


def _panel(panel_id: str, instrument_id: uuid.UUID | None, indicators=()) -> dict[str, Any]:
    return {
        "id": panel_id,
        "instrument_id": str(instrument_id) if instrument_id else None,
        "timeframe": "1h",
        "chart_type": "candles",
        "indicators": list(indicators),
        "strategies": [],
        "drawings": [],
    }


async def template_state(session: AsyncSession, template: Template) -> WorkspaceState:
    """``default``: BTC/USDT 1h with EMA 20 + EMA 50 and RSI 14, watchlist = the seeded crypto
    instruments that exist. ``blank``: BTC/USDT 1h without indicators. ``multi_chart``: 2x2 with
    BTC/ETH/BNB/SOL 1h. A seeded instrument that does not exist leaves its panel empty."""
    seeded = await _seeded(session, CRYPTO_SEEDS)
    btc = seeded["BTC/USDT"]
    if template == "multi_chart":
        symbols = ("BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT")
        doc = {
            "layout": {"type": "2x2", "sizes": [0.5, 0.5]},
            "sync": {"crosshair": True, "timeframe": True, "instrument": False},
            "panels": [_panel(f"p{i + 1}", seeded[s]) for i, s in enumerate(symbols)],
            "watchlist": [str(seeded[s]) for s in symbols if seeded[s]],
            "active_panel": "p1",
        }
    elif template == "blank":
        doc = {"layout": {"type": "1x1"}, "panels": [_panel("p1", btc)], "active_panel": "p1"}
    else:
        indicators = [
            {"id": "i1", "name": "ema", "params": {"length": 20}, "color": "#2962FF"},
            {"id": "i2", "name": "ema", "params": {"length": 50}, "color": "#FF6D00"},
            {"id": "i3", "name": "rsi", "params": {"length": 14}, "color": "#7E57C2"},
        ]
        doc = {
            "layout": {"type": "1x1", "sizes": [1.0]},
            "panels": [_panel("p1", btc, indicators)],
            "watchlist": [str(i) for i in seeded.values() if i],
            "active_panel": "p1",
        }
    state = WorkspaceState.model_validate(doc)
    assert not state_errors(state)  # resolves the indicator params
    return state


# --- reads -----------------------------------------------------------------------------------


async def ensure_default(session: AsyncSession, user: User) -> Workspace | None:
    """Create the default workspace when the user has none (once, also under concurrent first
    reads: the second waits for the lock and then sees the first one's row)."""
    if await _count(session, user.id):
        return None
    await _lock_user(session, user.id)
    if await _count(session, user.id):
        await session.commit()
        return None
    state = await template_state(session, "default")
    row = Workspace(
        user_id=user.id,
        name=DEFAULT_NAME,
        position=0,
        is_default=True,
        state=state.stored(),
        schema_version=SCHEMA_VERSION,
    )
    session.add(row)
    await session.commit()
    await publish(user.id, row.id, row.version, CREATED)
    return row


async def list_workspaces(session: AsyncSession, user: User) -> list[Workspace]:
    await ensure_default(session, user)
    rows = await session.scalars(
        select(Workspace)
        .where(Workspace.user_id == user.id)
        .order_by(Workspace.position, Workspace.created_at)
    )
    return list(rows.all())


def summary(row: Workspace) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "position": row.position,
        "is_default": row.is_default,
        "version": row.version,
        "panel_count": len(row.state.get("panels", [])),
        "is_shared": row.is_shared,
        "updated_at": row.updated_at,
    }


async def get_own_or_404(session: AsyncSession, user: User, workspace_id: uuid.UUID) -> Workspace:
    row = await session.get(Workspace, workspace_id, populate_existing=True)
    if row is None or row.user_id != user.id:  # never 403: do not leak that it exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return row


async def _annotated_state(
    session: AsyncSession, state: dict[str, Any], viewer_id: uuid.UUID | None = None
):
    """(state with read-only ``instrument``/``unavailable`` on each panel and ``unavailable``
    on each strategy overlay, unavailable instrument ids)."""
    usable = await _usable_custom(session, _custom_keys(state), viewer_id)
    refs = _instrument_refs(state)
    found = await _instruments(session, (i for _, i in refs))
    unavailable = []
    for _, instrument_id in refs:
        row = found.get(instrument_id)
        if (row is None or not row.is_active) and instrument_id not in unavailable:
            unavailable.append(instrument_id)
    panels = []
    for panel in state["panels"]:
        raw = panel.get("instrument_id")
        row = found.get(uuid.UUID(raw)) if raw else None
        info = None
        if row is not None:
            info = {
                "id": str(row.id),
                "symbol": row.symbol,
                "source": row.source,
                "is_active": row.is_active,
            }
        # deleted (no row) or deactivated; an empty panel (no instrument) is not unavailable
        missing = raw is not None and (row is None or not row.is_active)
        strategies = [
            {**s, "unavailable": _strategy_unavailable(s.get("strategy_key", ""), usable)}
            for s in panel.get("strategies", [])
        ]
        panels.append(
            {**panel, "instrument": info, "unavailable": missing, "strategies": strategies}
        )
    return {**state, "panels": panels}, unavailable


def _strategy_unavailable(key: str, usable: set[str]) -> bool:
    if key.lower().startswith(CUSTOM_PREFIX):
        return key.lower() not in usable
    return key not in ts.STRATEGIES  # a global strategy removed from the code


async def read(session: AsyncSession, row: Workspace) -> dict[str, Any]:
    state, unavailable = await _annotated_state(session, row.state, row.user_id)
    return {
        "id": row.id,
        "name": row.name,
        "position": row.position,
        "is_default": row.is_default,
        "version": row.version,
        "schema_version": row.schema_version,
        "is_shared": row.is_shared,
        "share_slug": row.share_slug,
        "state": state,
        "unavailable_instrument_ids": unavailable,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# --- writes ----------------------------------------------------------------------------------


async def _insert(
    session: AsyncSession, user: User, name: str, stored: dict[str, Any], *, explicit_name: bool
) -> Workspace:
    """Insert under the user lock (limit, unique name, position, default if first)."""
    await _lock_user(session, user.id)
    count = await _count(session, user.id)
    if count >= _limit(user):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"At most {_limit(user)} workspaces for your role"
        )
    if explicit_name:
        if await _name_taken(session, user.id, name):
            raise _duplicate_name()
    else:
        name = await _unique_name(session, user.id, name)
    row = Workspace(
        user_id=user.id,
        name=name,
        position=await _next_position(session, user.id),
        is_default=count == 0,
        state=stored,
        schema_version=SCHEMA_VERSION,
    )
    session.add(row)
    await _commit_or_conflict(session)
    await publish(user.id, row.id, row.version, CREATED)
    return row


async def create(session: AsyncSession, user: User, data: WorkspaceCreate) -> Workspace:
    if data.state is not None and data.template is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give either state or template, not both"
        )
    if data.state is not None:
        stored = await validate_state(session, data.state, user=user)
    else:
        stored = (await template_state(session, data.template or "blank")).stored()
    return await _insert(session, user, data.name, stored, explicit_name=True)


async def replace_state(
    session: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    state: WorkspaceState,
    version: int | None,
) -> Workspace:
    if version is None:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "Send the workspace version you edited (body field version or If-Match)",
        )
    current = await get_own_or_404(session, user, workspace_id)
    keep = {i for _, i in _instrument_refs(current.state)}
    stored = await validate_state(
        session, state, keep=keep, user=user, keep_custom=_custom_keys(current.state)
    )
    # atomic compare-and-set: no read-modify-write race between devices
    row = await session.scalar(
        update(Workspace)
        .where(
            Workspace.id == workspace_id,
            Workspace.user_id == user.id,
            Workspace.version == version,
        )
        .values(
            state=stored,
            schema_version=SCHEMA_VERSION,
            version=Workspace.version + 1,
            updated_at=func.now(),
        )
        .returning(Workspace)
        .execution_options(populate_existing=True)
    )
    if row is None:  # changed by another client since (or concurrently): report its version
        raise VersionConflict(await get_own_or_404(session, user, workspace_id))
    await session.commit()
    await publish(user.id, row.id, row.version, STATE_UPDATED)
    return row


async def _make_default(session: AsyncSession, row: Workspace) -> None:
    # unset the old default first: the partial unique index is checked per statement
    await session.execute(
        update(Workspace)
        .where(Workspace.user_id == row.user_id, Workspace.is_default, Workspace.id != row.id)
        .values(is_default=False)
    )
    row.is_default = True
    await session.flush()


async def patch(
    session: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    version: int | None,
) -> Workspace:
    await _lock_user(session, user.id)
    row = await get_own_or_404(session, user, workspace_id)
    if version is not None and version != row.version:
        raise VersionConflict(row)
    actions = []
    if data.name is not None and data.name != row.name:
        if await _name_taken(session, user.id, data.name, exclude=row.id):
            raise _duplicate_name()
        row.name = data.name
        actions.append(RENAMED)
    if data.is_default and not row.is_default:
        await _make_default(session, row)
        actions.append(DEFAULT_CHANGED)
    await _commit_or_conflict(session)
    await session.refresh(row)
    for action in actions:
        await publish(user.id, row.id, row.version, action)
    return row


async def duplicate(session: AsyncSession, user: User, workspace_id: uuid.UUID) -> Workspace:
    """A copy named "<name> (copy)" (or "(copy 2)", ...), not default, not shared."""
    source = await get_own_or_404(session, user, workspace_id)
    return await _insert(session, user, source.name, dict(source.state), explicit_name=False)


async def reorder(session: AsyncSession, user: User, ids: list[uuid.UUID]) -> list[Workspace]:
    await _lock_user(session, user.id)
    rows = {
        row.id: row
        for row in await session.scalars(select(Workspace).where(Workspace.user_id == user.id))
    }
    if len(ids) != len(set(ids)) or set(ids) != set(rows):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [
                error(
                    ("body", "ids"),
                    f"must list each of your {len(rows)} workspace ids exactly once",
                )
            ],
        )
    for position, workspace_id in enumerate(ids):
        rows[workspace_id].position = position
    await session.commit()
    await publish(user.id, None, None, REORDERED)
    return [rows[i] for i in ids]


async def delete(session: AsyncSession, user: User, workspace_id: uuid.UUID) -> None:
    """Deleting the default makes the first remaining one (by position) the default. Deleting
    the last one is allowed: the next list recreates the default workspace."""
    await _lock_user(session, user.id)
    row = await get_own_or_404(session, user, workspace_id)
    was_default = row.is_default
    await session.delete(row)
    await session.flush()
    successor = None
    if was_default:
        successor = await session.scalar(
            select(Workspace)
            .where(Workspace.user_id == user.id)
            .order_by(Workspace.position, Workspace.created_at)
            .limit(1)
        )
        if successor is not None:
            successor.is_default = True
    await session.commit()
    await publish(user.id, workspace_id, None, DELETED)
    if successor is not None:
        await publish(user.id, successor.id, successor.version, DEFAULT_CHANGED)


# --- sharing ---------------------------------------------------------------------------------


async def share(session: AsyncSession, user: User, workspace_id: uuid.UUID) -> Workspace:
    if user.role not in SHARE_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only analysts, experts and admins can share workspaces"
        )
    row = await get_own_or_404(session, user, workspace_id)
    if not row.is_shared:
        row.is_shared = True
        row.share_slug = secrets.token_urlsafe(12)  # 16 characters, 96 random bits
        await session.commit()
        await publish(user.id, row.id, row.version, SHARED)
    return row


async def unshare(session: AsyncSession, user: User, workspace_id: uuid.UUID) -> Workspace:
    row = await get_own_or_404(session, user, workspace_id)
    if row.is_shared:
        row.is_shared = False
        row.share_slug = None
        await session.commit()
        await publish(user.id, row.id, row.version, UNSHARED)
    return row


async def get_shared_or_404(session: AsyncSession, slug: str) -> tuple[Workspace, User]:
    found = (
        await session.execute(
            select(Workspace, User)
            .join(User, User.id == Workspace.user_id)
            .where(Workspace.share_slug == slug, Workspace.is_shared, User.is_active)
        )
    ).first()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shared workspace not found")
    return found[0], found[1]


async def read_shared(session: AsyncSession, slug: str) -> dict[str, Any]:
    row, owner = await get_shared_or_404(session, slug)
    state, unavailable = await _annotated_state(session, row.state)
    return {
        "name": row.name,
        "owner": {"display_name": owner.full_name or "Unnamed user", "role": owner.role.value},
        "schema_version": row.schema_version,
        "state": state,
        "unavailable_instrument_ids": unavailable,
        "updated_at": row.updated_at,
    }


async def import_shared(
    session: AsyncSession, user: User, slug: str, data: SharedImport
) -> Workspace:
    """Copy a shared workspace into the caller's own (their limit applies)."""
    row, _ = await get_shared_or_404(session, slug)
    if data.name is not None:
        return await _insert(session, user, data.name, dict(row.state), explicit_name=True)
    return await _insert(session, user, row.name, dict(row.state), explicit_name=False)
