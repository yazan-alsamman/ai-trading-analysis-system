"""Custom strategies (docs/custom-strategies.md). The definitions themselves are validated by
``trading_strategies.custom`` (Builder / Composite), not here."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.custom_strategy import CustomStrategyKind, Visibility

Name = Annotated[str, Field(min_length=1, max_length=60)]
Description = Annotated[str, Field(max_length=500)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomStrategyCreate(_Strict):
    name: Name
    description: Description = ""
    kind: CustomStrategyKind
    definition: dict[str, Any]
    visibility: Visibility = Visibility.private


class CustomStrategyReplace(_Strict):
    """Replace the definition (and optionally name/description). ``version`` is the version
    you edited; another client's change in between gives 409 with the current version."""

    version: int = Field(ge=1)
    definition: dict[str, Any]
    name: Name | None = None
    description: Description | None = None


class CustomStrategyUpdate(_Strict):
    name: Name | None = None
    description: Description | None = None
    visibility: Visibility | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        for field in ("name", "description", "visibility"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DefinitionIssue(BaseModel):
    path: str = Field(description="JSON path in the definition, e.g. buy.all[2].right")
    loc: list[str | int]
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[DefinitionIssue]
    history: int | None = Field(description="bars of warm-up needed (when valid)")
    definition: dict[str, Any] | None = Field(description="the normalised definition")
    definition_hash: str | None


class Usage(BaseModel):
    activations: int  # your /me/strategies rows using it
    active_activations: int
    backtests: int  # your backtests of it
    composites: int  # your composites that use it as a member


class CustomStrategySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str = Field(description="custom:<uuid>, the strategy_key everywhere else")
    name: str
    description: str
    kind: CustomStrategyKind
    visibility: Visibility
    version: int
    definition_hash: str
    cloned_from: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CustomStrategyRead(CustomStrategySummary):
    definition: dict[str, Any]
    valid: bool = Field(description="false if a member was deleted or made private")
    errors: list[DefinitionIssue]
    history: int | None
    usage: Usage


class Author(BaseModel):
    display_name: str
    role: str


class PublicCustomStrategy(BaseModel):
    """A public strategy as other users see it: no user ids."""

    id: uuid.UUID
    key: str
    name: str
    description: str
    kind: CustomStrategyKind
    definition: dict[str, Any]
    version: int
    author: Author
    created_at: datetime
    updated_at: datetime


class SchemaResponse(BaseModel):
    schema_version: int
    json_schema: dict[str, Any] = Field(description="JSON Schema of each kind's definition")
    catalog: dict[str, Any] = Field(
        description="indicators with params and outputs, price fields, ops with operands, "
        "composite modes and global strategies, limits"
    )
