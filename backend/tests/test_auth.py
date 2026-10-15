import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from tests.utils import DEFAULT_PASSWORD, bearer

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
TOKEN = "/api/v1/auth/token"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/users/me"


async def _refresh_rows(session: AsyncSession, user_id: uuid.UUID) -> list[RefreshToken]:
    session.expire_all()
    rows = await session.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id))
    return list(rows.all())


# --- register -------------------------------------------------------------------------------


async def test_register_ok(client: AsyncClient) -> None:
    res = await client.post(
        REGISTER,
        json={"email": "New.User@Example.com", "password": "abcdefg1", "full_name": "New User"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "new.user@example.com"
    assert body["role"] == "trader"
    assert body["is_active"] is True
    assert body["full_name"] == "New User"
    assert "hashed_password" not in body and "password" not in body


async def test_register_duplicate_email_409(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "abcdefg1"}
    assert (await client.post(REGISTER, json=payload)).status_code == 201
    payload["email"] = "DUP@example.com"
    res = await client.post(REGISTER, json=payload)
    assert res.status_code == 409


@pytest.mark.parametrize("password", ["short1", "allletters", "12345678", ""])
async def test_register_weak_password_422(client: AsyncClient, password: str) -> None:
    res = await client.post(REGISTER, json={"email": "weak@example.com", "password": password})
    assert res.status_code == 422


async def test_register_invalid_email_422(client: AsyncClient) -> None:
    res = await client.post(REGISTER, json={"email": "not-an-email", "password": "abcdefg1"})
    assert res.status_code == 422


async def test_register_ignores_role_in_payload(client: AsyncClient) -> None:
    res = await client.post(
        REGISTER,
        json={"email": "sneaky@example.com", "password": "abcdefg1", "role": "admin"},
    )
    assert res.status_code == 201
    assert res.json()["role"] == "trader"


# --- login ----------------------------------------------------------------------------------


async def test_login_ok(client: AsyncClient, make_user) -> None:
    await make_user("trader@example.com")
    res = await client.post(
        LOGIN, json={"email": "TRADER@example.com", "password": DEFAULT_PASSWORD}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_access_minutes * 60
    claims = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert claims["type"] == "access" and claims["role"] == "trader"
    assert {"sub", "iat", "exp"} <= claims.keys()


async def test_login_wrong_password_and_unknown_email_same_401(
    client: AsyncClient, make_user
) -> None:
    await make_user("trader@example.com")
    wrong_pw = await client.post(
        LOGIN, json={"email": "trader@example.com", "password": "nope1234"}
    )
    unknown = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "nope1234"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json() == {"detail": "Incorrect email or password"}


async def test_login_inactive_user_403(client: AsyncClient, make_user) -> None:
    await make_user("inactive@example.com", is_active=False)
    res = await client.post(
        LOGIN, json={"email": "inactive@example.com", "password": DEFAULT_PASSWORD}
    )
    assert res.status_code == 403


async def test_oauth2_token_form(client: AsyncClient, make_user) -> None:
    await make_user("form@example.com")
    res = await client.post(
        TOKEN, data={"username": "form@example.com", "password": DEFAULT_PASSWORD}
    )
    assert res.status_code == 200, res.text
    me = await client.get(ME, headers=bearer(res.json()["access_token"]))
    assert me.status_code == 200
    bad = await client.post(TOKEN, data={"username": "form@example.com", "password": "wrong123"})
    assert bad.status_code == 401


# --- /users/me with different tokens --------------------------------------------------------


async def test_me_valid_token(client: AsyncClient, make_user, login) -> None:
    user = await make_user("me@example.com")
    tokens = await login("me@example.com")
    res = await client.get(ME, headers=bearer(tokens["access_token"]))
    assert res.status_code == 200
    assert res.json()["id"] == str(user.id)


async def test_me_without_token_401(client: AsyncClient) -> None:
    assert (await client.get(ME)).status_code == 401


async def test_me_expired_token_401(client: AsyncClient, make_user) -> None:
    user = await make_user("expired@example.com")
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": "trader",
            "type": "access",
            "iat": past - timedelta(minutes=30),
            "exp": past,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    res = await client.get(ME, headers=bearer(token))
    assert res.status_code == 401
    assert res.json()["detail"] == "Token has expired"


async def test_me_garbage_token_401(client: AsyncClient) -> None:
    assert (await client.get(ME, headers=bearer("not.a.jwt"))).status_code == 401


async def test_me_token_with_wrong_signature_401(client: AsyncClient, make_user) -> None:
    user = await make_user("forged@example.com")
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": "admin",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "some-other-secret-that-is-long-enough",
        algorithm="HS256",
    )
    assert (await client.get(ME, headers=bearer(token))).status_code == 401


async def test_me_refresh_token_as_access_401(client: AsyncClient, make_user, login) -> None:
    await make_user("mixup@example.com")
    tokens = await login("mixup@example.com")
    res = await client.get(ME, headers=bearer(tokens["refresh_token"]))
    assert res.status_code == 401


async def test_access_token_cannot_be_used_to_refresh(
    client: AsyncClient, make_user, login
) -> None:
    await make_user("mixup2@example.com")
    tokens = await login("mixup2@example.com")
    res = await client.post(REFRESH, json={"refresh_token": tokens["access_token"]})
    assert res.status_code == 401


async def test_me_inactive_user_with_valid_token_403(
    client: AsyncClient, session: AsyncSession, make_user, login
) -> None:
    user = await make_user("soon-inactive@example.com")
    tokens = await login("soon-inactive@example.com")
    user.is_active = False
    await session.commit()
    res = await client.get(ME, headers=bearer(tokens["access_token"]))
    assert res.status_code == 403


async def test_update_me(client: AsyncClient, make_user, login) -> None:
    await make_user("rename@example.com")
    tokens = await login("rename@example.com")
    res = await client.patch(
        ME, json={"full_name": "Renamed"}, headers=bearer(tokens["access_token"])
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Renamed"
    # role/email are not editable through this endpoint
    res = await client.patch(
        ME, json={"role": "admin", "email": "x@example.com"}, headers=bearer(tokens["access_token"])
    )
    assert res.status_code == 200
    assert res.json()["role"] == "trader"
    assert res.json()["email"] == "rename@example.com"


# --- refresh / logout -----------------------------------------------------------------------


async def test_refresh_rotation(
    client: AsyncClient, session: AsyncSession, make_user, login
) -> None:
    user = await make_user("rotate@example.com")
    first = await login("rotate@example.com")

    res = await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})
    assert res.status_code == 200, res.text
    second = res.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await client.get(ME, headers=bearer(second["access_token"]))).status_code == 200

    old_jti = uuid.UUID(
        jwt.decode(first["refresh_token"], options={"verify_signature": False})["jti"]
    )
    new_jti = uuid.UUID(
        jwt.decode(second["refresh_token"], options={"verify_signature": False})["jti"]
    )
    rows = {r.id: r for r in await _refresh_rows(session, user.id)}
    assert rows[old_jti].revoked_at is not None
    assert rows[old_jti].replaced_by == new_jti
    assert rows[new_jti].revoked_at is None

    # the new refresh token keeps working
    res = await client.post(REFRESH, json={"refresh_token": second["refresh_token"]})
    assert res.status_code == 200


async def test_refresh_reuse_detection_revokes_all(
    client: AsyncClient, session: AsyncSession, make_user, login
) -> None:
    user = await make_user("reuse@example.com")
    first = await login("reuse@example.com")
    other_device = await login("reuse@example.com")
    second = (await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})).json()

    # replaying the already-rotated token is rejected...
    res = await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})
    assert res.status_code == 401
    # ...and every refresh token of that user is now revoked
    assert all(r.revoked_at is not None for r in await _refresh_rows(session, user.id))
    for token in (second["refresh_token"], other_device["refresh_token"]):
        assert (await client.post(REFRESH, json={"refresh_token": token})).status_code == 401


async def test_refresh_garbage_401(client: AsyncClient) -> None:
    assert (await client.post(REFRESH, json={"refresh_token": "garbage"})).status_code == 401


async def test_refresh_unknown_jti_401(client: AsyncClient, make_user) -> None:
    user = await make_user("nojti@example.com")
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user.id),
            "jti": str(uuid.uuid4()),
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(days=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert (await client.post(REFRESH, json={"refresh_token": token})).status_code == 401


async def test_logout(client: AsyncClient, make_user, login) -> None:
    await make_user("bye@example.com")
    tokens = await login("bye@example.com")
    headers = bearer(tokens["access_token"])
    body = {"refresh_token": tokens["refresh_token"]}

    assert (await client.post(LOGOUT, json=body)).status_code == 401  # needs auth
    assert (await client.post(LOGOUT, json=body, headers=headers)).status_code == 204
    assert (await client.post(LOGOUT, json=body, headers=headers)).status_code == 204  # idempotent
    assert (await client.post(REFRESH, json=body)).status_code == 401


async def test_logout_with_someone_elses_refresh_token_401(
    client: AsyncClient, make_user, login
) -> None:
    await make_user("alice@example.com")
    await make_user("bob@example.com")
    alice = await login("alice@example.com")
    bob = await login("bob@example.com")
    res = await client.post(
        LOGOUT,
        json={"refresh_token": bob["refresh_token"]},
        headers=bearer(alice["access_token"]),
    )
    assert res.status_code == 401
    assert (
        await client.post(REFRESH, json={"refresh_token": bob["refresh_token"]})
    ).status_code == 200


# --- password change ------------------------------------------------------------------------


async def test_password_change_revokes_refresh_tokens(
    client: AsyncClient, session: AsyncSession, make_user, login
) -> None:
    user = await make_user("pw@example.com")
    a = await login("pw@example.com")
    b = await login("pw@example.com")
    headers = bearer(a["access_token"])

    res = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "wrong-one1", "new_password": "NewPassw0rd"},
        headers=headers,
    )
    assert res.status_code == 400

    res = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "weak"},
        headers=headers,
    )
    assert res.status_code == 422

    res = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "NewPassw0rd"},
        headers=headers,
    )
    assert res.status_code == 204

    assert all(r.revoked_at is not None for r in await _refresh_rows(session, user.id))
    for t in (a, b):
        assert (
            await client.post(REFRESH, json={"refresh_token": t["refresh_token"]})
        ).status_code == 401
    old = await client.post(LOGIN, json={"email": "pw@example.com", "password": DEFAULT_PASSWORD})
    assert old.status_code == 401
    await login("pw@example.com", "NewPassw0rd")


async def test_user_role_enum_values(session: AsyncSession, make_user) -> None:
    for role in UserRole:
        await make_user(f"{role.value}@example.com", role=role)
    roles = await session.scalars(select(User.role).order_by(User.email))
    assert sorted(r.value for r in roles.all()) == ["admin", "analyst", "expert", "trader"]
