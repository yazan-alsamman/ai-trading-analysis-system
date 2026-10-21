"""Strategy keys -> runnable strategies, for preview, backtests, ``/me/strategies`` and the
live signal engine (instead of calling the ``trading_strategies`` registry directly).

- A global key (``ma_crossover``) resolves through the registry; ``params`` are validated.
- ``custom:<uuid>`` resolves to a custom strategy the caller may use: their own, or a public
  one (anything else is 404, so private strategies are never revealed). Custom strategies take
  no params; their ``params_hash`` is the definition hash, so an edit is a new setup.
- Custom members of a composite are resolved with the **composite owner's** access (their own
  strategies and public ones), recursively, and loaded from the database before the
  library's synchronous resolver runs.
- Signals follow the same rule (``visible_signal``): a ``custom:<uuid>`` signal is shown only
  to users who may use that strategy now (and to admins); global strategies' signals to all.
"""

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import trading_strategies as ts
from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, Text, cast, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from trading_strategies.composite import MAX_NESTING
from trading_strategies.custom import Validation

from app.models.custom_strategy import KEY_PREFIX, CustomStrategy, CustomStrategyKind, Visibility
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resolved:
    key: str
    strategy: ts.Strategy
    params: dict[str, Any]
    params_hash: str
    custom: CustomStrategy | None = None
    snapshot: dict[str, Any] | None = None  # custom only: rebuilds the strategy without the DB

    @property
    def name(self) -> str:
        return self.custom.name if self.custom is not None else self.strategy.title


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found")


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def is_custom(key: str) -> bool:
    return key.startswith(KEY_PREFIX)


def custom_id(key: str) -> uuid.UUID | None:
    """The id of a ``custom:<uuid>`` key; None for anything else (incl. a malformed id)."""
    if not is_custom(key):
        return None
    try:
        return uuid.UUID(key.removeprefix(KEY_PREFIX))
    except ValueError:
        return None


def can_use(row: CustomStrategy, user_id: uuid.UUID) -> bool:
    return row.user_id == user_id or row.visibility == Visibility.public


def sees_all_signals(user: User) -> bool:
    """Admins see every signal (moderation); everyone else only those of strategies they may
    use."""
    return user.role == UserRole.admin


def may_read_ai_setup(user: User, setup: object) -> bool:
    """Who may read (and size, and take) an AI setup. AI setups are global, not a custom
    strategy: everyone who may read signals may use them. The one place B12's isolation rules
    would change."""
    return True


def usable_keys(user_id: uuid.UUID):
    """SQL: the ``custom:<uuid>`` keys ``user_id`` may use (their own and public ones)."""
    return select(func.concat(KEY_PREFIX, cast(CustomStrategy.id, Text))).where(
        or_(CustomStrategy.user_id == user_id, CustomStrategy.visibility == Visibility.public)
    )


def visible_signal(key: ColumnElement[str], user: User) -> ColumnElement[bool]:
    """SQL condition: a signal with strategy key ``key`` is visible to ``user``. A custom key
    needs a strategy the user may use (a deleted one is hidden); global keys are visible to
    everyone. Used as a WHERE clause, so pagination and totals stay right."""
    if sees_all_signals(user):
        return true()
    key = func.coalesce(key, "")
    return or_(~key.startswith(KEY_PREFIX), key.in_(usable_keys(user.id)))


async def visible_keys(session: AsyncSession, keys: Iterable[str], user: User | None) -> set[str]:
    """The strategy keys among ``keys`` whose signals ``user`` may see (``None``: what every
    user may see, i.e. global and public strategies)."""
    keys = set(keys)
    if user is not None and sees_all_signals(user):
        return keys
    owners = await signal_owners(session, keys)
    return {
        key
        for key, owner in owners.items()
        if owner is None or (user is not None and owner == user.id)
    }


async def signal_owners(session: AsyncSession, keys: Iterable[str]) -> dict[str, uuid.UUID | None]:
    """Who may receive the live signals of these strategy keys: ``None`` for everyone (a
    global or a public custom strategy), else the owner of the private custom strategy. Keys
    of deleted (or malformed) custom strategies are missing: their signals go to no one."""
    out: dict[str, uuid.UUID | None] = {}
    ids = {}
    for key in set(keys):
        if not is_custom(key):
            out[key] = None
        elif (cid := custom_id(key)) is not None:
            ids[cid] = key
    if ids:
        rows = await session.execute(
            select(CustomStrategy.id, CustomStrategy.user_id, CustomStrategy.visibility).where(
                CustomStrategy.id.in_(list(ids))
            )
        )
        for cid, owner, visibility in rows.all():
            out[ids[cid]] = None if visibility == Visibility.public else owner
    return out


def member_refs(kind: CustomStrategyKind | str, definition: dict[str, Any]) -> set[str]:
    if kind != CustomStrategyKind.composite:
        return set()
    return {m["ref"] for m in definition.get("members", []) if is_custom(str(m.get("ref", "")))}


async def load_members(
    session: AsyncSession, refs: Iterable[str], owner_id: uuid.UUID
) -> dict[str, CustomStrategy]:
    """Every custom strategy reachable from ``refs`` that ``owner_id`` may use (their own and
    public ones), following composites a few levels deeper than the nesting limit so the
    library can report a too-deep nesting or a cycle itself."""
    found: dict[str, CustomStrategy] = {}
    pending = set(refs)
    for _ in range(MAX_NESTING + 2):
        ids = {i for ref in pending if ref not in found and (i := custom_id(ref)) is not None}
        if not ids:
            break
        rows = await session.scalars(select(CustomStrategy).where(CustomStrategy.id.in_(ids)))
        pending = set()
        for row in rows:
            if can_use(row, owner_id):
                found[row.key] = row
                pending |= member_refs(row.kind, row.definition)
    return found


def resolver(rows: dict[str, CustomStrategy]):
    """The library's resolver over preloaded rows (LookupError = unknown or inaccessible)."""

    def resolve(ref: str) -> tuple[str, dict[str, Any]]:
        row = rows.get(ref.lower())
        if row is None:
            raise LookupError(ref)
        return row.kind.value, row.definition

    return resolve


async def check(
    session: AsyncSession,
    kind: CustomStrategyKind | str,
    definition: Any,
    owner_id: uuid.UUID,
    *,
    key: str | None = None,
) -> Validation:
    """Validate a definition as ``owner_id``'s (members they may use); never raises."""
    refs: set[str] = set()
    if kind == CustomStrategyKind.composite and isinstance(definition, dict):
        members = definition.get("members")
        if isinstance(members, list):
            refs = {
                str(m["ref"]).lower()
                for m in members
                if isinstance(m, dict) and isinstance(m.get("ref"), str) and is_custom(m["ref"])
            }
    rows = await load_members(session, refs, owner_id) if refs else {}
    return ts.validate(str(kind), definition, resolver(rows), key=key)


async def resolve_custom_row(session: AsyncSession, row: CustomStrategy) -> Resolved:
    """A stored custom strategy as a runnable one (422 if it no longer validates, e.g. a
    member was deleted or made private)."""
    checked = await check(session, row.kind, row.definition, row.user_id, key=row.key)
    if not checked.valid:
        first = checked.errors[0]
        where = f"{first['path']}: " if first["path"] else ""
        raise _unprocessable(f"Custom strategy {row.name!r} cannot run: {where}{first['message']}")
    assert checked.snapshot is not None
    strategy = ts.from_snapshot(checked.snapshot, key=row.key, title=row.name)
    return Resolved(
        key=row.key,
        strategy=strategy,
        params={},
        params_hash=ts.snapshot_hash(checked.snapshot),
        custom=row,
        snapshot=checked.snapshot,
    )


async def get_custom_or_404(session: AsyncSession, key: str, user: User) -> CustomStrategy:
    cid = custom_id(key)
    row = await session.get(CustomStrategy, cid) if cid is not None else None
    if row is None or not can_use(row, user.id):
        raise not_found()
    return row


async def get(
    session: AsyncSession, key: str, user: User, params: dict[str, Any] | None = None
) -> Resolved:
    """Resolve ``key`` for ``user`` (404 for custom strategies they may not use, 422 for an
    unknown global key or invalid params)."""
    if is_custom(key):
        if params:
            raise _unprocessable("Custom strategies take no params (params must be empty)")
        return await resolve_custom_row(session, await get_custom_or_404(session, key, user))
    try:
        strategy = ts.get_strategy(key)
        resolved = strategy.resolve(params)
    except ValueError as exc:
        raise _unprocessable(str(exc)) from None
    return Resolved(key, strategy, resolved, ts.params_hash(key, resolved))


async def load_reachable(
    session: AsyncSession, rows: Iterable[CustomStrategy]
) -> dict[str, CustomStrategy]:
    """``rows`` and every custom strategy reachable from them through composites, one query per
    nesting level for all of them together (no access filter: the resolver applies it)."""
    found = {row.key: row for row in rows}
    pending = {ref for row in found.values() for ref in member_refs(row.kind, row.definition)}
    for _ in range(MAX_NESTING + 2):
        ids = {i for ref in pending if ref not in found and (i := custom_id(ref)) is not None}
        if not ids:
            break
        loaded = await session.scalars(select(CustomStrategy).where(CustomStrategy.id.in_(ids)))
        pending = set()
        for row in loaded:
            found[row.key] = row
            pending |= member_refs(row.kind, row.definition)
    return found


def _owner_resolver(rows: dict[str, CustomStrategy], owner_id: uuid.UUID):
    def resolve(ref: str) -> tuple[str, dict[str, Any]]:
        row = rows.get(ref.lower())
        if row is None or not can_use(row, owner_id):
            raise LookupError(ref)
        return row.kind.value, row.definition

    return resolve


async def engine_snapshots(session: AsyncSession, keys: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Custom keys -> ``{"snapshot", "params_hash", "name"}`` or ``{"error"}``, for the live
    engine: one query for the strategies and one per nesting level for their members, however
    many keys (the beat tick resolves all due jobs at once)."""
    keys = sorted(set(keys))
    ids = {cid: key for key in keys if (cid := custom_id(key)) is not None}
    out: dict[str, dict[str, Any]] = {
        key: {"error": "malformed custom key"} for key in keys if custom_id(key) is None
    }
    rows = []
    if ids:
        rows = list(
            await session.scalars(select(CustomStrategy).where(CustomStrategy.id.in_(list(ids))))
        )
    reachable = await load_reachable(session, rows)
    by_id = {row.id: row for row in rows}
    for cid, key in ids.items():
        row = by_id.get(cid)
        if row is None:
            out[key] = {"error": "custom strategy not found"}
            continue
        checked = ts.validate(
            row.kind.value, row.definition, _owner_resolver(reachable, row.user_id), key=row.key
        )
        if not checked.valid:
            first = checked.errors[0]
            where = f"{first['path']}: " if first["path"] else ""
            out[key] = {
                "error": f"Custom strategy {row.name!r} cannot run: {where}{first['message']}"
            }
            continue
        out[key] = {
            "snapshot": checked.snapshot,
            "params_hash": ts.snapshot_hash(checked.snapshot),
            "name": row.name,
        }
    return out


async def for_engine(
    session: AsyncSession,
    setups: Iterable[tuple[str, str, dict[str, Any]]],
    snapshots: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[Resolved], list[str]]:
    """The live engine's setups ``(strategy_key, params_hash, params)`` as runnable strategies,
    plus error messages for setups that cannot run (unknown key, invalid params, a custom
    strategy deleted or broken). Custom setups come from ``snapshots`` (resolved by the beat
    tick); keys missing there are resolved here in one batch. No caller access check:
    activations are checked when they are created and deactivated when a strategy is deleted
    or made private."""
    out: list[Resolved] = []
    errors: list[str] = []
    custom: list[str] = []
    for key, params_hash, params in setups:
        if is_custom(key):
            if key not in custom:
                custom.append(key)  # one setup per custom key: the current definition
            continue
        if key not in ts.STRATEGIES:
            continue  # a strategy removed from the code: nothing to run
        strategy = ts.get_strategy(key)
        try:
            strategy.history(params)  # stored params still valid for the strategy?
        except ValueError as exc:
            errors.append(f"{key}: {exc}")
            continue
        out.append(Resolved(key, strategy, params, params_hash))
    known = dict(snapshots or {})
    missing = [k for k in custom if k not in known]
    if missing:
        known.update(await engine_snapshots(session, missing))
    for key in custom:
        entry = known[key]
        if "error" in entry:
            errors.append(f"{key}: {entry['error']}")
            continue
        strategy = ts.from_snapshot(entry["snapshot"], key=key, title=entry.get("name"))
        out.append(Resolved(key, strategy, {}, entry["params_hash"], snapshot=entry["snapshot"]))
    return out, errors
