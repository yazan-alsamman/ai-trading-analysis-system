"""Posts, comments, likes, follows, profiles and reports (docs/news-posts.md). JWT only."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.api.limits import COST_KEY
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.social import PostDirection, ReportStatus
from app.schemas.common import Page
from app.schemas.posts import (
    AdminReportRead,
    CommentCreate,
    CommentRead,
    CommentUpdate,
    FollowRead,
    FollowState,
    LikeState,
    PostCreate,
    PostRead,
    PostUpdate,
    ProfileRead,
    ReportCreate,
    ReportRead,
    ReportResolve,
    ThreadRead,
)
from app.social import service

router = APIRouter(tags=["posts"])
admin_router = APIRouter(prefix="/admin/reports", tags=["posts"])

CREATE_COST = {COST_KEY: get_settings().content_create_cost}


async def _one(session, user, post) -> dict:
    return (await service.serialize_posts(session, user, [post]))[0]


# --- posts ---------------------------------------------------------------------------------------


@router.get("/posts", response_model=Page[PostRead])
async def list_posts(
    user: CurrentUser,
    session: SessionDep,
    scope: Literal["all", "following"] = "all",
    instrument_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None,
    direction: PostDirection | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The feed, newest first. ``scope=following``: authors you follow only. Followers-only
    posts appear for the author's followers; your own hidden posts appear with their status."""
    posts, total = await service.feed(
        session,
        user,
        scope=scope,
        instrument_id=instrument_id,
        author_id=author_id,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    items = await service.serialize_posts(session, user, posts)
    return Page[PostRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/posts",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=CREATE_COST,
)
async def create_post(data: PostCreate, user: CurrentUser, session: SessionDep):
    """Analysts, experts and admins. Followers get a ``new_post`` notification."""
    post = await service.create_post(session, user, data)
    return await _one(session, user, post)


@router.get("/posts/{post_id}", response_model=PostRead)
async def get_post(post_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    return await _one(session, user, await service.visible_post(session, user, post_id))


@router.patch("/posts/{post_id}", response_model=PostRead)
async def update_post(post_id: uuid.UUID, data: PostUpdate, user: CurrentUser, session: SessionDep):
    """The author within 24 hours of publishing; admins at any time."""
    post = await service.visible_post(session, user, post_id)
    post = await service.update_post(session, user, post, data)
    return await _one(session, user, post)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    post = await service.visible_post(session, user, post_id)
    await service.delete_post(session, user, post)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/like", response_model=LikeState)
async def like_post(post_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Idempotent."""
    post = await service.visible_post(session, user, post_id)
    return await service.like(session, get_redis(), user, post)


@router.delete("/posts/{post_id}/like", response_model=LikeState)
async def unlike_post(post_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Idempotent."""
    post = await service.visible_post(session, user, post_id)
    return await service.unlike(session, user, post)


# --- comments ------------------------------------------------------------------------------------


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    parent_id: Annotated[
        uuid.UUID | None, Query(description="all replies of one top-level comment, paginated")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ThreadRead] | Page[CommentRead]:
    """Top-level comments oldest first, each with up to 20 replies inline (``more_replies``
    when there are more: fetch them with ``parent_id``)."""
    post = await service.visible_post(session, user, post_id)
    if parent_id is not None:
        items, total = await service.replies_page(
            session, user, post, parent_id, limit=limit, offset=offset
        )
        return Page[CommentRead](items=items, total=total, limit=limit, offset=offset)
    items, total = await service.threads(session, user, post, limit=limit, offset=offset)
    return Page[ThreadRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=CREATE_COST,
)
async def create_comment(
    post_id: uuid.UUID, data: CommentCreate, user: CurrentUser, session: SessionDep
):
    post = await service.visible_post(session, user, post_id)
    comment = await service.create_comment(session, get_redis(), user, post, data)
    return service.serialize_comment(user, comment, {user.id: user})


@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: uuid.UUID, data: CommentUpdate, user: CurrentUser, session: SessionDep
):
    comment = await service.own_comment(session, user, comment_id)
    comment = await service.update_comment(session, user, comment, data.body)
    return service.serialize_comment(user, comment, {user.id: user})


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    comment = await service.own_comment(session, user, comment_id)
    await service.delete_comment(session, user, comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- follows and profiles ------------------------------------------------------------------------


@router.post("/users/{user_id}/follow", response_model=FollowState)
async def follow(user_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Idempotent. Only analysts and experts can be followed; 400 for yourself."""
    return await service.follow(session, user, user_id)


@router.delete("/users/{user_id}/follow", response_model=FollowState)
async def unfollow(user_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    return await service.unfollow(session, user, user_id)


@router.get("/users/{user_id}/profile", response_model=ProfileRead)
async def get_profile(user_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    return await service.profile(session, user, user_id)


@router.get("/me/following", response_model=Page[FollowRead])
async def my_following(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await service.follow_list(
        session, user, followers=False, limit=limit, offset=offset
    )
    return Page[FollowRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/me/followers", response_model=Page[FollowRead])
async def my_followers(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await service.follow_list(
        session, user, followers=True, limit=limit, offset=offset
    )
    return Page[FollowRead](items=items, total=total, limit=limit, offset=offset)


# --- reports -------------------------------------------------------------------------------------


@router.post(
    "/reports",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=CREATE_COST,
)
async def create_report(
    data: ReportCreate, user: CurrentUser, session: SessionDep, response: Response
):
    """201 for a new report, 200 with the existing one if you already reported this content."""
    row, created = await service.report(session, user, data)
    if not created:
        response.status_code = status.HTTP_200_OK
    return row


@admin_router.get("", response_model=Page[AdminReportRead])
async def list_reports(
    _: AdminUser,
    session: SessionDep,
    report_status: Annotated[Literal["open", "resolved", "all"], Query(alias="status")] = "open",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await service.list_reports(
        session,
        report_status=None if report_status == "all" else ReportStatus(report_status),
        limit=limit,
        offset=offset,
    )
    return Page[AdminReportRead](items=items, total=total, limit=limit, offset=offset)


@admin_router.post("/{report_id}/resolve", response_model=ReportRead)
async def resolve_report(
    report_id: uuid.UUID, data: ReportResolve, admin: AdminUser, session: SessionDep
):
    """``hide``: the post or comment disappears for everyone but its author (who is notified);
    ``dismiss``: no change. All open reports on the same content are resolved."""
    return await service.resolve(session, get_redis(), admin, report_id, data)
