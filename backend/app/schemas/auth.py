from typing import Literal

from pydantic import BaseModel

from app.schemas.user import NormalizedEmail


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # access token lifetime in seconds


class RefreshRequest(BaseModel):
    refresh_token: str
