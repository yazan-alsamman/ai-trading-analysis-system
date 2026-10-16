"""Custom strategies (docs/custom-strategies.md): your own Builder and Composite strategies
(/me/custom-strategies, JWT only), public ones of other users, and the schema/validation the
web and mobile editors are built from.

A custom strategy is used everywhere a global one is, with the key ``custom:<uuid>``:
``POST /strategies/{key}/preview``, ``POST /backtests`` and ``POST /me/strategies``.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Query, status

from app.api.deps import CurrentUser, SessionDep, StrategiesReader
from app.api.limits import COST_KEY
from app.core.config import get_settings
from app.models.custom_strategy import CustomStrategyKind
from app.schemas.common import Page
from app.schemas.custom_strategies import (
    CustomStrategyCreate,
    CustomStrategyRead,
    CustomStrategyReplace,
    CustomStrategySummary,
    CustomStrategyUpdate,
    PublicCustomStrategy,
    SchemaResponse,
    ValidateResponse,
)
from app.services import custom_strategy_service as service

router = APIRouter(prefix="/me/custom-strategies", tags=["custom-strategies"])
public_router = APIRouter(prefix="/custom-strategies", tags=["custom-strategies"])

VALIDATE_COST = {COST_KEY: get_settings().rate_limit_validate_cost}


# --- schema, validation, public ---------------------------------------------------------------


@public_router.get("/schema", response_model=SchemaResponse)
async def definition_schema(_: StrategiesReader):
    """JSON Schema of the Builder and Composite definitions, plus the catalog an editor needs:
    indicators (params, outputs), price fields, ops with their operands, composite modes and
    global strategies, and every limit."""
    return service.schema()


@public_router.post("/validate", response_model=ValidateResponse, openapi_extra=VALIDATE_COST)
async def validate_definition(
    user: CurrentUser,
    session: SessionDep,
    payload: Annotated[
        Any,
        Body(
            description="{kind: builder|composite, definition: {...}, id?: uuid of the strategy "
            "being edited (cycle detection)}",
            examples=[{"kind": "builder", "definition": {"schema_version": 1}}],
        ),
    ] = None,
):
    """Check a definition without saving it. Always 200: ``{valid, errors[], history}``, each
    error with the JSON path of the problem (``buy.all[2].right.params.length``)."""
    return await service.validate(session, user, payload)


@public_router.get("/public", response_model=Page[PublicCustomStrategy])
async def public_strategies(
    _: StrategiesReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=60, description="part of the name")] = None,
    kind: CustomStrategyKind | None = None,
):
    """Public strategies of all users, most recently updated first, with the author's display
    name and role (no user ids)."""
    items, total = await service.list_public(
        session, limit=limit, offset=offset, search=search, kind=kind
    )
    return Page[PublicCustomStrategy](items=items, total=total, limit=limit, offset=offset)


@public_router.post(
    "/public/{strategy_id}/clone",
    response_model=CustomStrategyRead,
    status_code=status.HTTP_201_CREATED,
)
async def clone_public_strategy(strategy_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Copy a public strategy into your own list (private; your limit applies)."""
    row = await service.clone_public(session, user, strategy_id)
    return await service.read(session, user, row)


# --- your strategies --------------------------------------------------------------------------


@router.get("", response_model=Page[CustomStrategySummary])
async def my_custom_strategies(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: CustomStrategyKind | None = None,
):
    rows, total = await service.list_mine(session, user, limit=limit, offset=offset, kind=kind)
    return Page[CustomStrategySummary](
        items=[service.summary(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=CustomStrategyRead, status_code=status.HTTP_201_CREATED)
async def create_custom_strategy(
    data: CustomStrategyCreate, user: CurrentUser, session: SessionDep
):
    """422 with every definition error (``loc``/``path``), 409 name taken, 400 over your
    role's limit, 403 ``public`` for traders."""
    row = await service.create(session, user, data)
    return await service.read(session, user, row)


@router.get("/{strategy_id}", response_model=CustomStrategyRead)
async def get_custom_strategy(strategy_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """With ``key`` (``custom:<uuid>``), whether it can still run, and usage counts."""
    row = await service.get_own_or_404(session, user, strategy_id)
    return await service.read(session, user, row)


@router.put("/{strategy_id}", response_model=CustomStrategyRead)
async def replace_custom_strategy(
    strategy_id: uuid.UUID, data: CustomStrategyReplace, user: CurrentUser, session: SessionDep
):
    """Replace the definition (``version`` = the one you edited; 409 with the current version
    if it changed meanwhile). Active setups follow the new definition from the next bar."""
    row = await service.replace(session, user, strategy_id, data)
    return await service.read(session, user, row)


@router.patch("/{strategy_id}", response_model=CustomStrategyRead)
async def update_custom_strategy(
    strategy_id: uuid.UUID, data: CustomStrategyUpdate, user: CurrentUser, session: SessionDep
):
    """Name, description, visibility (``public``: analysts, experts and admins)."""
    row = await service.patch(session, user, strategy_id, data)
    return await service.read(session, user, row)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_strategy(strategy_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Deactivates its activations; signals and backtests are kept. 409 if one of your
    composites uses it."""
    await service.delete(session, user, strategy_id)


@router.post(
    "/{strategy_id}/clone", response_model=CustomStrategyRead, status_code=status.HTTP_201_CREATED
)
async def clone_custom_strategy(strategy_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """A private copy named "<name> (copy)"."""
    row = await service.clone_own(session, user, strategy_id)
    return await service.read(session, user, row)
