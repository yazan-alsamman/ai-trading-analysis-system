import uuid

import pytest
from httpx import AsyncClient

from app.models.user import UserRole
from tests.utils import bearer

USERS = "/api/v1/admin/users"


@pytest.fixture
async def admin_headers(make_user, login) -> dict[str, str]:
    await make_user("admin@example.com", role=UserRole.admin)
    return bearer((await login("admin@example.com"))["access_token"])


async def _id_of(client: AsyncClient, headers: dict[str, str]) -> str:
    return (await client.get("/api/v1/users/me", headers=headers)).json()["id"]


async def test_list_users_pagination_and_filters(
    client: AsyncClient, make_user, admin_headers
) -> None:
    await make_user("t1@example.com")
    await make_user("t2@example.com")
    await make_user("analyst@example.com", role=UserRole.analyst)
    await make_user("off@example.com", is_active=False)

    res = await client.get(USERS, headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5 and body["limit"] == 20 and body["offset"] == 0
    assert len(body["items"]) == 5
    assert all("hashed_password" not in u for u in body["items"])

    res = await client.get(USERS, params={"limit": 2, "offset": 1}, headers=admin_headers)
    body = res.json()
    assert body["total"] == 5 and len(body["items"]) == 2 and body["offset"] == 1

    res = await client.get(USERS, params={"role": "analyst"}, headers=admin_headers)
    assert [u["email"] for u in res.json()["items"]] == ["analyst@example.com"]

    res = await client.get(USERS, params={"is_active": "false"}, headers=admin_headers)
    assert [u["email"] for u in res.json()["items"]] == ["off@example.com"]

    res = await client.get(USERS, params={"q": "T1"}, headers=admin_headers)
    assert [u["email"] for u in res.json()["items"]] == ["t1@example.com"]

    # LIKE wildcards in q are matched literally
    res = await client.get(USERS, params={"q": "%"}, headers=admin_headers)
    assert res.json()["total"] == 0


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}, {"role": "x"}])
async def test_list_users_invalid_params_422(
    client: AsyncClient, admin_headers, params: dict
) -> None:
    assert (await client.get(USERS, params=params, headers=admin_headers)).status_code == 422


@pytest.mark.parametrize("role", [UserRole.trader, UserRole.analyst, UserRole.expert])
async def test_admin_endpoints_forbidden_for_non_admin(
    client: AsyncClient, make_user, login, role: UserRole
) -> None:
    target = await make_user("target@example.com")
    await make_user("user@example.com", role=role)
    headers = bearer((await login("user@example.com"))["access_token"])

    assert (await client.get(USERS, headers=headers)).status_code == 403
    res = await client.patch(f"{USERS}/{target.id}/role", json={"role": "admin"}, headers=headers)
    assert res.status_code == 403
    res = await client.patch(
        f"{USERS}/{target.id}/status", json={"is_active": False}, headers=headers
    )
    assert res.status_code == 403


async def test_admin_endpoints_require_auth(client: AsyncClient) -> None:
    some_id = uuid.uuid4()
    assert (await client.get(USERS)).status_code == 401
    res = await client.patch(f"{USERS}/{some_id}/role", json={"role": "admin"})
    assert res.status_code == 401
    res = await client.patch(f"{USERS}/{some_id}/status", json={"is_active": False})
    assert res.status_code == 401


async def test_update_role(client: AsyncClient, make_user, login, admin_headers) -> None:
    target = await make_user("promote@example.com")
    target_headers = bearer((await login("promote@example.com"))["access_token"])
    assert (await client.get(USERS, headers=target_headers)).status_code == 403

    res = await client.patch(
        f"{USERS}/{target.id}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["role"] == "analyst"

    res = await client.patch(
        f"{USERS}/{target.id}/role", json={"role": "admin"}, headers=admin_headers
    )
    assert res.json()["role"] == "admin"
    # the role is read from the DB, so the user's existing access token picks it up immediately
    assert (await client.get(USERS, headers=target_headers)).status_code == 200


async def test_update_role_errors(client: AsyncClient, admin_headers) -> None:
    res = await client.patch(
        f"{USERS}/{uuid.uuid4()}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert res.status_code == 404
    admin_id = await _id_of(client, admin_headers)
    res = await client.patch(
        f"{USERS}/{admin_id}/role", json={"role": "boss"}, headers=admin_headers
    )
    assert res.status_code == 422


async def test_admin_cannot_demote_self(client: AsyncClient, admin_headers) -> None:
    admin_id = await _id_of(client, admin_headers)
    for role in ("trader", "analyst", "expert"):
        res = await client.patch(
            f"{USERS}/{admin_id}/role", json={"role": role}, headers=admin_headers
        )
        assert res.status_code == 400
    # re-asserting admin on self is a no-op, not an error
    res = await client.patch(
        f"{USERS}/{admin_id}/role", json={"role": "admin"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert (await client.get(USERS, headers=admin_headers)).status_code == 200


async def test_update_status(client: AsyncClient, make_user, login, admin_headers) -> None:
    target = await make_user("victim@example.com")
    tokens = await login("victim@example.com")

    res = await client.patch(
        f"{USERS}/{target.id}/status", json={"is_active": False}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # deactivated: refresh tokens revoked, access token rejected, login rejected
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401
    me = await client.get("/api/v1/users/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 403
    res = await client.post(
        "/api/v1/auth/login", json={"email": "victim@example.com", "password": "Passw0rd123"}
    )
    assert res.status_code == 403

    res = await client.patch(
        f"{USERS}/{target.id}/status", json={"is_active": True}, headers=admin_headers
    )
    assert res.status_code == 200 and res.json()["is_active"] is True
    await login("victim@example.com")

    res = await client.patch(
        f"{USERS}/{uuid.uuid4()}/status", json={"is_active": False}, headers=admin_headers
    )
    assert res.status_code == 404


async def test_admin_cannot_deactivate_self(client: AsyncClient, admin_headers) -> None:
    admin_id = await _id_of(client, admin_headers)
    res = await client.patch(
        f"{USERS}/{admin_id}/status", json={"is_active": False}, headers=admin_headers
    )
    assert res.status_code == 400
    assert (await client.get(USERS, headers=admin_headers)).status_code == 200
