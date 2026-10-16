import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.expert import BIO_MAX, HEADLINE_MAX, PlanInterval, SubscriptionStatus
from app.models.user import UserRole
from app.social import markdown

MARKETS = ("crypto", "forex", "gold", "commodities", "stocks", "indices")
LANGUAGE_CODES = ("ar", "en", "fr", "de", "es", "tr")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _bio(v: str) -> str:
    return markdown.check(v) if v else ""


def _line(v: str) -> str:
    v = markdown.check(v, single_line=True)
    if not v:
        raise ValueError("must not be empty")
    return v


class ExpertProfileIn(_Strict):
    headline: Annotated[str, Field(min_length=1, max_length=HEADLINE_MAX), AfterValidator(_line)]
    bio: Annotated[str, Field(max_length=BIO_MAX), AfterValidator(_bio)] = ""
    markets: list[Literal[MARKETS]] = Field(default_factory=list, max_length=len(MARKETS))  # type: ignore[valid-type]
    languages: list[Literal[LANGUAGE_CODES]] = Field(  # type: ignore[valid-type]
        default_factory=list, max_length=len(LANGUAGE_CODES)
    )
    chat_enabled: bool = True
    response_time_hint: Annotated[str, Field(max_length=60)] | None = None
    is_listed: bool = True

    @field_validator("markets", "languages")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return sorted(set(v))


class ExpertProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    headline: str
    bio: str
    markets: list[str]
    languages: list[str]
    chat_enabled: bool
    response_time_hint: str | None
    is_listed: bool
    created_at: datetime
    updated_at: datetime


class Perks(_Strict):
    premium_posts: bool = True
    chat: bool = True
    signals_feed: bool = False


Price = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=12, decimal_places=2)]


class PlanIn(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=60), AfterValidator(_line)]
    description: Annotated[str, Field(max_length=1000), AfterValidator(_bio)] = ""
    price: Price
    currency: Literal["USD", "EUR"] = "USD"
    interval: PlanInterval
    trial_days: Annotated[int, Field(ge=0, le=30)] = 0
    perks: Perks = Field(default_factory=Perks)
    is_active: bool = True


class PlanUpdate(_Strict):
    """A new price only applies to new subscriptions and to renewals (docs/subscriptions.md)."""

    name: Annotated[str, Field(min_length=1, max_length=60), AfterValidator(_line)] | None = None
    description: Annotated[str, Field(max_length=1000), AfterValidator(_bio)] | None = None
    price: Price | None = None
    trial_days: Annotated[int, Field(ge=0, le=30)] | None = None
    perks: Perks | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expert_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str
    interval: PlanInterval
    trial_days: int
    perks: dict[str, bool]
    is_active: bool
    created_at: datetime


class PlanBrief(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    currency: str
    interval: PlanInterval
    trial_days: int


class PersonRef(BaseModel):
    id: uuid.UUID
    display_name: str
    role: UserRole


class ExpertCard(BaseModel):
    id: uuid.UUID
    display_name: str
    headline: str
    markets: list[str]
    languages: list[str]
    chat_enabled: bool
    response_time_hint: str | None
    followers_count: int
    subscribers_count: int
    rating: float | None = Field(default=None, description="placeholder, always null for now")
    cheapest_plan: PlanBrief | None
    is_subscribed: bool


class ExpertDetail(ExpertCard):
    bio: str
    member_since: datetime
    plans: list[PlanRead]
    entitlements: dict[str, bool]
    recent_posts: list[dict[str, Any]]


class CheckoutRequest(_Strict):
    plan_id: uuid.UUID
    return_url: Annotated[str, Field(max_length=500)] | None = Field(
        default=None, description="where the payment page sends the browser (an allowed origin)"
    )


class CheckoutRead(BaseModel):
    checkout_id: uuid.UUID
    checkout_url: str = Field(description="absolute with PUBLIC_BASE_URL, else a path")
    checkout_path: str
    status: str
    expires_at: datetime


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    kind: str
    amount: Decimal
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    failure_reason: str | None
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime


class SubscriptionRead(BaseModel):
    id: uuid.UUID
    expert: PersonRef
    plan: dict[str, Any]
    status: SubscriptionStatus
    price: Decimal
    currency: str
    interval: PlanInterval
    perks: dict[str, bool]
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    canceled_at: datetime | None
    next_charge_at: datetime | None
    grace_ends_at: datetime | None
    ended_at: datetime | None
    payment_method: dict[str, Any] | None
    created_at: datetime
    invoices: list[InvoiceRead]


class AdminSubscriptionRead(BaseModel):
    id: uuid.UUID
    user: PersonRef
    expert: PersonRef
    plan_id: uuid.UUID
    status: SubscriptionStatus
    price: Decimal
    currency: str
    interval: PlanInterval
    current_period_end: datetime
    cancel_at_period_end: bool
    past_due_since: datetime | None
    ended_at: datetime | None
    created_at: datetime


class FastForward(_Strict):
    to: Literal["period_end", "grace_end"] = "period_end"


class FastForwardResult(BaseModel):
    outcome: str
    subscription: AdminSubscriptionRead


class MonthRevenue(BaseModel):
    month: str  # 2026-10
    gross: Decimal
    platform_fee: Decimal
    net: Decimal
    refunded: Decimal
    invoices: int


class EarningsInvoice(BaseModel):
    number: str
    kind: str
    amount: Decimal
    currency: str
    status: str
    platform_fee: Decimal | None
    net: Decimal | None
    subscriber: str
    plan: str
    paid_at: datetime | None
    created_at: datetime


class EarningsRead(BaseModel):
    currency: str
    platform_fee_pct: float
    active_subscribers: int
    by_status: dict[str, int]
    mrr: Decimal = Field(description="monthly recurring revenue of paying subscriptions")
    churn_30d_pct: float | None
    ended_30d: int
    months: list[MonthRevenue]
    recent_invoices: list[EarningsInvoice]
