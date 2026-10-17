"""Step 7: an analyst posts, a trader follows and comments, both are notified."""

import time


def test_post_comment_notifications(http, make_account):
    analyst, trader = make_account("analyst"), make_account("trader")
    assert http.post(f"/users/{analyst.id}/follow", headers=trader.h).status_code == 200
    res = http.post(
        "/posts",
        json={
            "title": "E2E: BTC outlook",
            "body": "## Plan\n\nWatching **64k**.",
            "visibility": "public",
        },
        headers=analyst.h,
    )
    assert res.status_code == 201, res.text
    post_id = res.json()["id"]
    res = http.post(f"/posts/{post_id}/comments", json={"body": "Thanks!"}, headers=trader.h)
    assert res.status_code == 201, res.text
    inbox = http.get("/me/notifications", params={"type": "comment_reply"}, headers=analyst.h)
    assert inbox.json()["total"] == 1
    # new_post reaches followers through a Celery task on the notifications queue
    deadline = time.time() + 30
    while True:
        res = http.get("/me/notifications", params={"type": "new_post"}, headers=trader.h)
        if res.json()["total"] >= 1:
            break
        assert time.time() < deadline, "new_post notification not delivered"
        time.sleep(1)
