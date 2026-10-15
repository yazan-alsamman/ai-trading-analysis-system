import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.api_key import Scope

Name = Annotated[str, Field(min_length=1, max_length=100)]
Scopes = Annotated[
    list[Scope],
    Field(min_length=1, description="market:read, indicators:read, strategies:read, ..."),
    AfterValidator(lambda v: sorted(set(v))),  # duplicates are dropped
]
RateLimit = Annotated[int, Field(ge=1, description="requests per minute, at most your tier")]


class ApiKeyCreate(BaseModel):
    name: Name
    scopes: Scopes
    expires_in_days: Annotated[int, Field(ge=1, le=3650)] | None = None
    rate_limit_per_minute: RateLimit | None = None  # None = the owner's tier


class ApiKeyUpdate(BaseModel):
    name: Name | None = None
    scopes: Scopes | None = None
    rate_limit_per_minute: RateLimit | None = None  # explicit null = back to the owner's tier

    @model_validator(mode="after")
    def _no_null_for_required(self) -> Self:
        for field in ("name", "scopes"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ApiKeyRead(BaseModel):
    """Never contains the key or its hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    rate_limit_per_minute: int | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


class ApiKeyCreated(ApiKeyRead):
    key: str = Field(description="The full key. Shown only in this response: store it now.")


class AdminApiKeyRead(ApiKeyRead):
    user_id: uuid.UUID
    owner_email: str


class ApiKeyUsageDay(BaseModel):
    date: date
    requests: int  # allowed requests
    rejected: int  # requests answered with 429
