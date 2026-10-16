"""Custom strategies: CRUD, per-role limits, visibility, cloning and what an edit or a delete
does to everything that uses the strategy.

- Structural changes of one user's strategies (create, clone) take a per-user advisory lock, so
  the limit and the unique name hold when two requests race.
- A definition change (``PUT``) is optimistic: ``UPDATE ... WHERE version = :v`` bumps the
  version; a stale version gets 409 with the current one.
- ``definition_hash`` is the hash of the strategy's snapshot (for a composite, including its
  custom members' definitions). When it changes, the activations of the strategy follow the
  new hash from the next bar (old signals keep theirs), and every composite that contains it is
  re-hashed the same way, transitively.
- A composite that can no longer run (a member deleted or made private) has its activations
  deactivated; signals and backtests are always kept.
"""

import uuid
from collections.abc import Sequence
from typing import Any

import trading_strategies as ts
from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from trading_strategies.custom import Validation

from app.core.config import get_settings
from app.models.backtest import Backtest
from app.models.custom_strategy import CustomStrategy, CustomStrategyKind, Visibility
from app.models.strategy import UserStrategy
from app.models.user import User, UserRole
from app.schemas.custom_strategies import (
    CustomStrategyCreate,
    CustomStrategyReplace,
    CustomStrategyUpdate,
)
from app.services import strategy_resolver
from app.services.workspace_service import VersionConflict

PUBLISH_ROLES = frozenset({UserRole.analyst, UserRole.expert, UserRole.admin})
MAX_CASCADE = 50  # composites re-hashed after one edit (nesting is at most 3 levels)


class CustomStrategyVersionConflict(VersionConflict):
    """409 with the current version (the VersionConflict handler in app.main)."""

    def body(self) -> dict[str, Any]:
        return {
            "detail": "Custom strategy was changed by another client; reload it and apply your "
            "change again",
            "current_version": self.current_version,
            "updated_at": self.updated_at.isoformat(),
        }


# --- helpers ---------------------------------------------------------------------------------


async def _lock_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"custom_strategies:{user_id}"},
    )


def _limit(user: User) -> int:
    return get_settings().custom_strategy_limit(user.role.value)


def _duplicate_name() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "You already have a custom strategy with this name"
    )


async def _name_taken(
    session: AsyncSession, user_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    query = select(CustomStrategy.id).where(
        CustomStrategy.user_id == user_id, func.lower(CustomStrategy.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(CustomStrategy.id != exclude)
    return (await session.scalar(query.limit(1))) is not None


async def _unique_name(
    session: AsyncSession, user_id: uuid.UUID, base: str, *, keep_base: bool = False
) -> str:
    """``base (copy)``, ``base (copy 2)``, ... within 60 characters (``base`` itself first if
    ``keep_base`` and it is free)."""
    if keep_base and not await _name_taken(session, user_id, base):
        return base
    for n in range(1, 1000):
        suffix = " (copy)" if n == 1 else f" (copy {n})"
        candidate = base[: 60 - len(suffix)].rstrip() + suffix
        if not await _name_taken(session, user_id, candidate):
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, "Could not find a free name for the copy")


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "uq_custom_strategies_user_name" in str(exc.orig):
            raise _duplicate_name() from None
        raise


def http_errors(checked: Validation, prefix: tuple[str, ...] = ("body", "definition")) -> list:
    """Library issues as FastAPI-style 422 details (``loc``, ``msg``, ``type``) plus ``path``."""
    return [
        {
            "loc": [*prefix, *e["loc"]],
            "msg": e["message"],
            "type": "value_error",
            "path": e["path"],
        }
        for e in checked.errors
    ]


async def _validated(
    session: AsyncSession,
    owner_id: uuid.UUID,
    kind: CustomStrategyKind,
    definition: dict[str, Any],
    key: str | None = None,
) -> Validation:
    checked = await strategy_resolver.check(session, kind, definition, owner_id, key=key)
    if not checked.valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, http_errors(checked))
    return checked


async def validate(session: AsyncSession, user: User, payload: Any) -> dict[str, Any]:
    """``POST /custom-strategies/validate``: never raises for bad input."""
    if not isinstance(payload, dict):
        issue = {"path": "", "loc": [], "message": "expected an object {kind, definition}"}
        return _validation_body(Validation(errors=[issue]))
    unknown = sorted(set(payload) - {"kind", "definition", "id"})
    if unknown:
        issue = {"path": unknown[0], "loc": [unknown[0]], "message": "unknown field"}
        return _validation_body(Validation(errors=[issue]))
    kind = payload.get("kind")
    key = None
    if payload.get("id") is not None:
        try:
            key = f"custom:{uuid.UUID(str(payload['id']))}"
        except ValueError:
            issue = {"path": "id", "loc": ["id"], "message": "must be a UUID"}
            return _validation_body(Validation(errors=[issue]))
    if kind not in ("builder", "composite"):
        issue = {"path": "kind", "loc": ["kind"], "message": "must be one of builder, composite"}
        return _validation_body(Validation(errors=[issue]))
    checked = await strategy_resolver.check(
        session, kind, payload.get("definition"), user.id, key=key
    )
    return _validation_body(checked)


def _validation_body(checked: Validation) -> dict[str, Any]:
    return {
        "valid": checked.valid,
        "errors": checked.errors,
        "history": checked.history,
        "definition": checked.definition,
        "definition_hash": ts.snapshot_hash(checked.snapshot) if checked.snapshot else None,
    }


def schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "json_schema": ts.json_schemas(),
        "catalog": ts.operand_catalog(),
    }


# --- reads -----------------------------------------------------------------------------------


async def list_mine(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    kind: CustomStrategyKind | None = None,
) -> tuple[Sequence[CustomStrategy], int]:
    conditions = [CustomStrategy.user_id == user.id]
    if kind is not None:
        conditions.append(CustomStrategy.kind == kind)
    total = await session.scalar(
        select(func.count()).select_from(CustomStrategy).where(*conditions)
    )
    rows = await session.scalars(
        select(CustomStrategy)
        .where(*conditions)
        .order_by(CustomStrategy.created_at, CustomStrategy.id)
        .limit(limit)
        .offset(offset)
    )
    return rows.all(), total or 0


async def get_own_or_404(
    session: AsyncSession, user: User, strategy_id: uuid.UUID
) -> CustomStrategy:
    row = await session.get(CustomStrategy, strategy_id, populate_existing=True)
    if row is None or row.user_id != user.id:  # never 403: do not reveal it exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom strategy not found")
    return row


async def _direct_dependents(session: AsyncSession, key: str) -> list[CustomStrategy]:
    """Composites (of any user) with ``key`` as a member."""
    rows = await session.scalars(
        select(CustomStrategy)
        .where(
            CustomStrategy.kind == CustomStrategyKind.composite,
            CustomStrategy.definition.contains({"members": [{"ref": key}]}),
        )
        .order_by(CustomStrategy.created_at, CustomStrategy.id)
    )
    return list(rows.all())


async def _all_dependents(session: AsyncSession, key: str) -> list[CustomStrategy]:
    """Composites containing ``key`` directly or through other composites, nearest first."""
    out: dict[uuid.UUID, CustomStrategy] = {}
    frontier = [key]
    while frontier and len(out) < MAX_CASCADE:
        found = []
        for k in frontier:
            for row in await _direct_dependents(session, k):
                if row.id not in out and row.key != key:
                    out[row.id] = row
                    found.append(row.key)
        frontier = found
    return list(out.values())


async def usage(session: AsyncSession, user: User, row: CustomStrategy) -> dict[str, int]:
    counts = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(UserStrategy.is_active.is_(True)),
            ).where(UserStrategy.user_id == user.id, UserStrategy.strategy_key == row.key)
        )
    ).one()
    backtests = await session.scalar(
        select(func.count())
        .select_from(Backtest)
        .where(Backtest.user_id == user.id, Backtest.strategy_key == row.key)
    )
    composites = [r for r in await _direct_dependents(session, row.key) if r.user_id == user.id]
    return {
        "activations": counts[0],
        "active_activations": counts[1],
        "backtests": backtests or 0,
        "composites": len(composites),
    }


async def read(session: AsyncSession, user: User, row: CustomStrategy) -> dict[str, Any]:
    checked = await strategy_resolver.check(
        session, row.kind, row.definition, row.user_id, key=row.key
    )
    return {
        **summary(row),
        "definition": row.definition,
        "valid": checked.valid,
        "errors": checked.errors,
        "history": checked.history,
        "usage": await usage(session, user, row),
    }


def summary(row: CustomStrategy) -> dict[str, Any]:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "kind": row.kind,
        "visibility": row.visibility,
        "version": row.version,
        "definition_hash": row.definition_hash,
        "cloned_from": row.cloned_from,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def list_public(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: str | None = None,
    kind: CustomStrategyKind | None = None,
) -> tuple[list[dict[str, Any]], int]:
    conditions = [CustomStrategy.visibility == Visibility.public, User.is_active.is_(True)]
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(CustomStrategy.name.ilike(pattern, escape="\\"))
    if kind is not None:
        conditions.append(CustomStrategy.kind == kind)
    base = select(CustomStrategy, User).join(User, User.id == CustomStrategy.user_id)
    total = await session.scalar(
        select(func.count())
        .select_from(CustomStrategy)
        .join(User, User.id == CustomStrategy.user_id)
        .where(*conditions)
    )
    rows = await session.execute(
        base.where(*conditions)
        .order_by(CustomStrategy.updated_at.desc(), CustomStrategy.id)
        .limit(limit)
        .offset(offset)
    )
    return [public_view(s, u) for s, u in rows.all()], total or 0


def public_view(row: CustomStrategy, owner: User) -> dict[str, Any]:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "kind": row.kind,
        "definition": row.definition,
        "version": row.version,
        "author": {"display_name": owner.full_name or "Unnamed user", "role": owner.role.value},
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# --- visibility rules ------------------------------------------------------------------------


def _check_publish_role(user: User) -> None:
    if user.role not in PUBLISH_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only analysts, experts and admins can make custom strategies public",
        )


async def _check_members_public(
    session: AsyncSession, owner_id: uuid.UUID, kind: CustomStrategyKind, definition: dict
) -> None:
    """A public composite may only contain public custom strategies (directly or not), so
    everyone who can see it can also run it, and nothing private leaks through it."""
    refs = strategy_resolver.member_refs(kind, definition)
    rows = await strategy_resolver.load_members(session, refs, owner_id)
    private = sorted(r.name for r in rows.values() if r.visibility != Visibility.public)
    if private:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A public composite can only contain public custom strategies; make these public "
            f"first: {', '.join(private)}",
        )


# --- cascade -----------------------------------------------------------------------------------


async def _deactivate(
    session: AsyncSession, key: str, *, except_user: uuid.UUID | None = None
) -> int:
    query = (
        update(UserStrategy)
        .where(UserStrategy.strategy_key == key, UserStrategy.is_active.is_(True))
        .values(is_active=False, updated_at=func.now())
    )
    if except_user is not None:
        query = query.where(UserStrategy.user_id != except_user)
    result = await session.execute(query)
    return result.rowcount or 0


async def _set_hash(session: AsyncSession, row: CustomStrategy, new_hash: str) -> None:
    """The strategy's activations follow the new hash (from the next bar on)."""
    row.definition_hash = new_hash
    await session.execute(
        update(UserStrategy)
        .where(UserStrategy.strategy_key == row.key)
        .values(params_hash=new_hash, updated_at=func.now())
    )


async def refresh_dependents(session: AsyncSession, key: str) -> None:
    """After ``key`` changed (definition, visibility, deletion), re-check every composite that
    contains it: still valid -> re-hash it (and its activations) if its snapshot changed;
    no longer valid -> deactivate its activations."""
    for row in await _all_dependents(session, key):
        checked = await strategy_resolver.check(
            session, row.kind, row.definition, row.user_id, key=row.key
        )
        if not checked.valid:
            await _deactivate(session, row.key)
            continue
        assert checked.snapshot is not None
        new_hash = ts.snapshot_hash(checked.snapshot)
        if new_hash != row.definition_hash:
            await _set_hash(session, row, new_hash)
    await session.flush()


# --- writes ----------------------------------------------------------------------------------


async def _insert(
    session: AsyncSession,
    user: User,
    *,
    name: str,
    description: str,
    kind: CustomStrategyKind,
    definition: dict[str, Any],
    visibility: Visibility = Visibility.private,
    cloned_from: uuid.UUID | None = None,
    explicit_name: bool = True,
    keep_base: bool = False,
) -> CustomStrategy:
    checked = await _validated(session, user.id, kind, definition)
    if visibility == Visibility.public:
        _check_publish_role(user)
        await _check_members_public(session, user.id, kind, checked.definition or {})
    await _lock_user(session, user.id)
    count = await session.scalar(
        select(func.count()).select_from(CustomStrategy).where(CustomStrategy.user_id == user.id)
    )
    if count >= _limit(user):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"At most {_limit(user)} custom strategies for your role"
        )
    if explicit_name:
        if await _name_taken(session, user.id, name):
            raise _duplicate_name()
    else:
        name = await _unique_name(session, user.id, name, keep_base=keep_base)
    assert checked.snapshot is not None
    row = CustomStrategy(
        user_id=user.id,
        name=name,
        description=description,
        kind=kind,
        definition=checked.definition,
        definition_hash=ts.snapshot_hash(checked.snapshot),
        visibility=visibility,
        cloned_from=cloned_from,
    )
    session.add(row)
    await _commit(session)
    return row


async def create(session: AsyncSession, user: User, data: CustomStrategyCreate) -> CustomStrategy:
    return await _insert(
        session,
        user,
        name=data.name,
        description=data.description,
        kind=data.kind,
        definition=data.definition,
        visibility=data.visibility,
    )


async def replace(
    session: AsyncSession, user: User, strategy_id: uuid.UUID, data: CustomStrategyReplace
) -> CustomStrategy:
    current = await get_own_or_404(session, user, strategy_id)
    if data.version != current.version:
        raise CustomStrategyVersionConflict(current)
    checked = await _validated(session, user.id, current.kind, data.definition, key=current.key)
    assert checked.snapshot is not None and checked.definition is not None
    if current.visibility == Visibility.public:
        await _check_members_public(session, user.id, current.kind, checked.definition)
    if data.name is not None and await _name_taken(session, user.id, data.name, current.id):
        raise _duplicate_name()
    changed = checked.definition != current.definition
    values: dict[str, Any] = {"updated_at": func.clock_timestamp()}
    if changed:
        values.update(definition=checked.definition, version=CustomStrategy.version + 1)
    if data.name is not None:
        values["name"] = data.name
    if data.description is not None:
        values["description"] = data.description
    # atomic compare-and-set: no read-modify-write race between devices
    row = await session.scalar(
        update(CustomStrategy)
        .where(
            CustomStrategy.id == strategy_id,
            CustomStrategy.user_id == user.id,
            CustomStrategy.version == data.version,
        )
        .values(**values)
        .returning(CustomStrategy)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise CustomStrategyVersionConflict(await get_own_or_404(session, user, strategy_id))
    new_hash = ts.snapshot_hash(checked.snapshot)
    if new_hash != row.definition_hash:
        await _set_hash(session, row, new_hash)
        await refresh_dependents(session, row.key)
    await _commit(session)
    return row


async def patch(
    session: AsyncSession, user: User, strategy_id: uuid.UUID, data: CustomStrategyUpdate
) -> CustomStrategy:
    row = await get_own_or_404(session, user, strategy_id)
    if data.name is not None and data.name != row.name:
        if await _name_taken(session, user.id, data.name, exclude=row.id):
            raise _duplicate_name()
        row.name = data.name
    if data.description is not None:
        row.description = data.description
    made_private = False
    if data.visibility is not None and data.visibility != row.visibility:
        if data.visibility == Visibility.public:
            _check_publish_role(user)
            await _check_members_public(session, user.id, row.kind, row.definition)
        else:
            mine = [
                r.name
                for r in await _direct_dependents(session, row.key)
                if r.user_id == user.id and r.visibility == Visibility.public
            ]
            if mine:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Used by your public composite(s): {', '.join(mine)}; make them private first",
                )
            made_private = True
        row.visibility = data.visibility
    await session.flush()
    if made_private:  # other users may no longer use it
        await _deactivate(session, row.key, except_user=user.id)
        await refresh_dependents(session, row.key)
    await _commit(session)
    await session.refresh(row)
    return row


async def delete(session: AsyncSession, user: User, strategy_id: uuid.UUID) -> None:
    """Deactivates every activation of it (signals and backtests stay). 409 if one of your
    composites still uses it."""
    row = await get_own_or_404(session, user, strategy_id)
    mine = [r.name for r in await _direct_dependents(session, row.key) if r.user_id == user.id]
    if mine:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Used by your composite(s): {', '.join(mine)}; remove it from them first",
        )
    key = row.key
    await _deactivate(session, key)
    await session.delete(row)
    await session.flush()
    await refresh_dependents(session, key)  # other users' composites with it can no longer run
    await session.commit()


async def clone_own(session: AsyncSession, user: User, strategy_id: uuid.UUID) -> CustomStrategy:
    source = await get_own_or_404(session, user, strategy_id)
    return await _clone(session, user, source, keep_base=False)


async def get_public_or_404(session: AsyncSession, strategy_id: uuid.UUID) -> CustomStrategy:
    row = await session.scalar(
        select(CustomStrategy)
        .join(User, User.id == CustomStrategy.user_id)
        .where(
            CustomStrategy.id == strategy_id,
            CustomStrategy.visibility == Visibility.public,
            User.is_active.is_(True),
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Public custom strategy not found")
    return row


async def clone_public(session: AsyncSession, user: User, strategy_id: uuid.UUID) -> CustomStrategy:
    source = await get_public_or_404(session, strategy_id)
    return await _clone(session, user, source, keep_base=source.user_id != user.id)


async def _clone(
    session: AsyncSession, user: User, source: CustomStrategy, *, keep_base: bool
) -> CustomStrategy:
    """A private copy with ``cloned_from`` set, named "<name> (copy)" (or "(copy 2)", ...);
    a public strategy of someone else keeps its name if it is free. Custom members of a
    composite are referenced, not copied."""
    return await _insert(
        session,
        user,
        name=source.name,
        description=source.description,
        kind=source.kind,
        definition=dict(source.definition),
        cloned_from=source.id,
        explicit_name=False,
        keep_base=keep_base,
    )
