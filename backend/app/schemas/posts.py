import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models.candle import Timeframe
from app.models.social import (
    COMMENT_BODY_MAX,
    POST_BODY_MAX,
    TITLE_MAX,
    ContentStatus,
    PostDirection,
    PostVisibility,
    ReportStatus,
    ReportTarget,
)
from app.models.user import UserRole
from app.social import markdown

MAX_ATTACHMENTS = 5


def _title(v: str) -> str:
    v = markdown.check(v, single_line=True)
    if not v:
        raise ValueError("must not be empty")
    return v


def _body(v: str) -> str:
    v = markdown.check(v)
    if not v:
        raise ValueError("must not be empty")
    return v


Title = Annotated[str, Field(min_length=1, max_length=TITLE_MAX), AfterValidator(_title)]
PostBody = Annotated[str, Field(min_length=1, max_length=POST_BODY_MAX), AfterValidator(_body)]
CommentBody = Annotated[
    str, Field(min_length=1, max_length=COMMENT_BODY_MAX), AfterValidator(_body)
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


AttachmentType = Literal["backtest", "custom_strategy", "shared_workspace", "signal"]


class AttachmentRef(_Strict):
    type: AttachmentType
    id: uuid.UUID


class PostCreate(_Strict):
    title: Title
    body: PostBody = Field(description="Markdown, stored as written (raw HTML is refused)")
    instrument_id: uuid.UUID | None = None
    timeframe: Timeframe | None = None
    direction: PostDirection | None = None
    attachments: list[AttachmentRef] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)
    visibility: PostVisibility = PostVisibility.public


class PostUpdate(_Strict):
    title: Title | None = None
    body: PostBody | None = None
    instrument_id: uuid.UUID | None = None
    timeframe: Timeframe | None = None
    direction: PostDirection | None = None
    attachments: list[AttachmentRef] | None = Field(default=None, max_length=MAX_ATTACHMENTS)
    visibility: PostVisibility | None = None

    @model_validator(mode="after")
    def _required(self) -> Self:
        for name in ("title", "body", "attachments", "visibility"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class AuthorRead(BaseModel):
    id: uuid.UUID
    display_name: str
    role: UserRole


class InstrumentRef(BaseModel):
    id: uuid.UUID
    symbol: str


class PostRead(BaseModel):
    id: uuid.UUID
    author: AuthorRead
    title: str
    body: str
    instrument: InstrumentRef | None
    timeframe: Timeframe | None
    direction: PostDirection | None
    attachments: list[dict[str, Any]] = Field(
        description="resolved: {type, id, available, ...summary}; unavailable ones keep type/id"
    )
    visibility: PostVisibility
    status: ContentStatus
    comments_count: int
    likes_count: int
    liked_by_me: bool
    can_edit: bool
    edited_at: datetime | None
    created_at: datetime


class LikeState(BaseModel):
    liked: bool
    likes_count: int


class CommentCreate(_Strict):
    body: CommentBody
    parent_id: uuid.UUID | None = Field(
        default=None, description="a reply; a reply to a reply is stored under the top comment"
    )


class CommentUpdate(_Strict):
    body: CommentBody


class CommentRead(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    parent_id: uuid.UUID | None
    author: AuthorRead | None = Field(description="null for deleted comments")
    body: str | None = Field(description="null when deleted, or hidden (except for its author)")
    status: ContentStatus
    created_at: datetime
    edited_at: datetime | None
    can_edit: bool


class ThreadRead(CommentRead):
    replies: list[CommentRead]
    replies_count: int
    more_replies: bool


class FollowRead(BaseModel):
    user: AuthorRead
    since: datetime


class FollowState(BaseModel):
    following: bool
    followers_count: int


class StrategyRef(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    kind: str
    updated_at: datetime


class ProfileRead(BaseModel):
    id: uuid.UUID
    display_name: str
    role: UserRole
    member_since: datetime
    posts_count: int
    followers_count: int
    following_count: int
    followable: bool
    is_following: bool
    recent_posts: list[PostRead]
    public_strategies: list[StrategyRef]


class ReportCreate(_Strict):
    target_type: ReportTarget
    target_id: uuid.UUID
    reason: Annotated[str, Field(min_length=3, max_length=500)]


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: ReportTarget
    target_id: uuid.UUID
    reason: str
    status: ReportStatus
    resolution: str | None
    created_at: datetime
    resolved_at: datetime | None


class AdminReportRead(ReportRead):
    reporter: AuthorRead | None
    target: dict[str, Any] | None = Field(
        description="excerpt of the reported content: {status, author, title?, excerpt, post_id}"
    )
    open_reports_on_target: int


class ReportResolve(_Strict):
    action: Literal["hide", "dismiss"]
    note: Annotated[str, Field(max_length=300)] | None = Field(
        default=None, description="sent to the author with the hide notification"
    )
