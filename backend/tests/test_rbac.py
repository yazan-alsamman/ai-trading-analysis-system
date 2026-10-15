from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import require_roles
from app.core.security import create_access_token
from app.db.session import get_session
from app.models.user import User, UserRole
from tests.utils import bearer


def _build_app() -> FastAPI:
    """A throwaway app with one route per role, plus an analyst-or-expert route."""
    rbac_app = FastAPI()

    def add_route(path: str, *roles: UserRole) -> None:
        @rbac_app.get(path)
        async def route(user: Annotated[User, Depends(require_roles(*roles))]) -> dict:
            return {"role": user.role.value}

    for role in UserRole:
        add_route(f"/only/{role.value}", role)
    add_route("/analyst-or-expert", UserRole.analyst, UserRole.expert)
    return rbac_app


@pytest.fixture
async def rbac_client(session_factory):
    rbac_app = _build_app()

    async def _get_test_session():
        async with session_factory() as s:
            yield s

    rbac_app.dependency_overrides[get_session] = _get_test_session
    async with AsyncClient(transport=ASGITransport(app=rbac_app), base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("user_role", list(UserRole))
@pytest.mark.parametrize("required", list(UserRole))
async def test_require_single_role(
    rbac_client: AsyncClient, make_user, user_role: UserRole, required: UserRole
) -> None:
    user = await make_user(f"{user_role.value}@example.com", role=user_role)
    res = await rbac_client.get(
        f"/only/{required.value}", headers=bearer(create_access_token(user))
    )
    allowed = user_role == required or user_role == UserRole.admin
    assert res.status_code == (200 if allowed else 403), (user_role, required)


@pytest.mark.parametrize(
    ("user_role", "status"),
    [
        (UserRole.trader, 403),
        (UserRole.analyst, 200),
        (UserRole.expert, 200),
        (UserRole.admin, 200),
    ],
)
async def test_require_any_of_roles(
    rbac_client: AsyncClient, make_user, user_role: UserRole, status: int
) -> None:
    user = await make_user(f"{user_role.value}@example.com", role=user_role)
    res = await rbac_client.get("/analyst-or-expert", headers=bearer(create_access_token(user)))
    assert res.status_code == status


async def test_require_roles_needs_authentication(rbac_client: AsyncClient) -> None:
    assert (await rbac_client.get("/only/trader")).status_code == 401
