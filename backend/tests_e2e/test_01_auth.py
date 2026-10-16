"""Step 1: register -> login -> refresh -> API key with scopes (and its limits)."""

from tests_e2e.conftest import PASSWORD, login, register


def test_register_login_refresh_api_key(http, world, make_account):
    email = register(http, "auth")
    account = login(http, email, PASSWORD)
    res = http.post("/auth/refresh", json={"refresh_token": account.refresh})
    assert res.status_code == 200, res.text
    rotated = res.json()
    assert rotated["refresh_token"] != account.refresh
    # the old refresh token is spent: presenting it again is refused
    assert http.post("/auth/refresh", json={"refresh_token": account.refresh}).status_code == 401
    # ... and treated as theft: the rotated one was revoked with it
    assert (
        http.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code
        == 401
    )
    headers = {"Authorization": f"Bearer {rotated['access_token']}"}  # access tokens stay valid
    res = http.post(
        "/me/api-keys",
        json={"name": "e2e bot", "scopes": ["market:read", "news:read"]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    key = {"X-API-Key": res.json()["key"]}
    assert http.get("/market/instruments", headers=key).status_code == 200
    assert http.get("/signals", headers=key).status_code == 403  # no signals:read
    assert http.get("/users/me", headers=key).status_code == 403  # keys never reach accounts
    for role in ("trader", "analyst", "expert"):  # the accounts of the next steps
        make_account(role)
    assert {"trader", "analyst", "expert"} <= set(world.users)
