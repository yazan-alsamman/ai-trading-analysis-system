"""Workspaces (saved trading screens): /me/workspaces (JWT only) and shared read-only links.

Concurrency between devices: docs/workspaces.md.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.workspaces import (
    SharedImport,
    SharedWorkspaceRead,
    ShareRead,
    WorkspaceCreate,
    WorkspaceOrder,
    WorkspaceRead,
    WorkspaceStateUpdate,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from app.services import workspace_service as service

router = APIRouter(prefix="/me/workspaces", tags=["workspaces"])
shared_router = APIRouter(prefix="/workspaces/shared", tags=["workspaces"])

IfMatch = Annotated[
    str | None, Header(description='The version you edited, e.g. "3" (instead of body version)')
]


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = f'"{version}"'


@router.get("", response_model=list[WorkspaceSummary])
async def list_workspaces(user: CurrentUser, session: SessionDep):
    """Your workspaces in tab order. A user without any gets the default one created first."""
    return [service.summary(row) for row in await service.list_workspaces(session, user)]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate, user: CurrentUser, session: SessionDep, response: Response
):
    """From ``state``, or from ``template`` (default / blank / multi_chart; blank if neither)."""
    row = await service.create(session, user, data)
    _etag(response, row.version)
    return await service.read(session, row)


# declared before /{workspace_id} so "order" is not parsed as an id
@router.put("/order", response_model=list[WorkspaceSummary])
async def reorder_workspaces(data: WorkspaceOrder, user: CurrentUser, session: SessionDep):
    """``ids`` = all of your workspace ids, in the new tab order."""
    return [service.summary(row) for row in await service.reorder(session, user, data.ids)]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep, response: Response
):
    row = await service.get_own_or_404(session, user, workspace_id)
    _etag(response, row.version)
    return await service.read(session, row)


@router.put("/{workspace_id}", response_model=WorkspaceRead)
async def replace_workspace_state(
    workspace_id: uuid.UUID,
    data: WorkspaceStateUpdate,
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    if_match: IfMatch = None,
):
    """Replace the whole ``state``. Needs the version you edited (409 if it changed since)."""
    version = service.pick_version(data.version, if_match)
    row = await service.replace_state(session, user, workspace_id, data.state, version)
    _etag(response, row.version)
    return await service.read(session, row)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    if_match: IfMatch = None,
):
    """Rename, or make it the default (the previous default is unset in the same transaction)."""
    version = service.pick_version(data.version, if_match)
    row = await service.patch(session, user, workspace_id, data, version)
    _etag(response, row.version)
    return await service.read(session, row)


@router.post(
    "/{workspace_id}/duplicate", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED
)
async def duplicate_workspace(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    row = await service.duplicate(session, user, workspace_id)
    return await service.read(session, row)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await service.delete(session, user, workspace_id)


@router.post("/{workspace_id}/share", response_model=ShareRead)
async def share_workspace(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Analysts, experts and admins: a read-only link ``/workspaces/shared/{share_slug}``."""
    row = await service.share(session, user, workspace_id)
    return ShareRead(is_shared=row.is_shared, share_slug=row.share_slug)


@router.delete("/{workspace_id}/share", response_model=ShareRead)
async def unshare_workspace(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    row = await service.unshare(session, user, workspace_id)
    return ShareRead(is_shared=row.is_shared, share_slug=row.share_slug)


@shared_router.get("/{slug}", response_model=SharedWorkspaceRead)
async def get_shared_workspace(slug: str, _: CurrentUser, session: SessionDep):
    """Read-only; shows the owner's display name and role, never user ids."""
    return await service.read_shared(session, slug)


@shared_router.post(
    "/{slug}/import", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED
)
async def import_shared_workspace(
    slug: str, user: CurrentUser, session: SessionDep, data: SharedImport | None = None
):
    """Copy a shared workspace into your own (your workspace limit applies)."""
    row = await service.import_shared(session, user, slug, data or SharedImport())
    return await service.read(session, row)
