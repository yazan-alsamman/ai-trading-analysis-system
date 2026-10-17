"""Step 5: a workspace saved from two "devices": the stale save gets 409."""


def test_workspace_version_conflict(http, make_account):
    trader = make_account("trader")
    res = http.post(
        "/me/workspaces", json={"name": "E2E desk", "template": "multi_chart"}, headers=trader.h
    )
    assert res.status_code == 201, res.text
    ws = res.json()
    url = f"/me/workspaces/{ws['id']}"
    res = http.put(url, json={"state": ws["state"], "version": ws["version"]}, headers=trader.h)
    assert res.status_code == 200, res.text
    assert res.json()["version"] == ws["version"] + 1
    stale = http.put(url, json={"state": ws["state"], "version": ws["version"]}, headers=trader.h)
    assert stale.status_code == 409
    assert stale.json()["current_version"] == ws["version"] + 1
