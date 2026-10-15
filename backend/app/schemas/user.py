import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def validate_password_strength(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


Password = Annotated[
    str,
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(validate_password_strength),
]
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]
FullName = Annotated[str, Field(min_length=1, max_length=200)]


class UserCreate(BaseModel):
    # Unknown fields (e.g. "role") are ignored: self-registration always creates a trader.
    email: NormalizedEmail
    password: Password
    full_name: FullName | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: FullName | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class RoleUpdate(BaseModel):
    role: UserRole


class StatusUpdate(BaseModel):
    is_active: bool
