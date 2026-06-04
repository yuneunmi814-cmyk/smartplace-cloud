from datetime import datetime, timedelta, timezone

from tests._helpers import setup_targets


def test_dispatch_enqueues(client, user_token, auth, fakes):
    _, place_ids, _, image_id = setup_targets(client, auth, user_token)
    r = client.post(
        "/api/v1/tasks/dispatch",
        headers=auth(user_token),
        json={"imageId": image_id, "placeIds": place_ids},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    assert len(body["items"]) == 2
    assert fakes.queue.size() == 1


def test_future_schedule_not_enqueued(client, user_token, auth, fakes):
    _, place_ids, _, image_id = setup_targets(client, auth, user_token)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = client.post(
        "/api/v1/tasks/dispatch",
        headers=auth(user_token),
        json={"imageId": image_id, "placeIds": place_ids, "scheduledAt": future},
    )
    assert r.json()["status"] == "pending"
    assert fakes.queue.size() == 0


def test_dispatch_rejects_foreign_place(client, user_token, admin_token, auth):
    _, _, _, image_id = setup_targets(client, auth, user_token, place_count=1)
    # A place that belongs to the admin, not the user.
    _, admin_places, _, _ = setup_targets(client, auth, admin_token, place_count=1)
    r = client.post(
        "/api/v1/tasks/dispatch",
        headers=auth(user_token),
        json={"imageId": image_id, "placeIds": admin_places},
    )
    assert r.status_code == 400


def test_cancel_queued_task(client, user_token, auth):
    _, place_ids, _, image_id = setup_targets(client, auth, user_token, place_count=1)
    task_id = client.post(
        "/api/v1/tasks/dispatch",
        headers=auth(user_token),
        json={"imageId": image_id, "placeIds": place_ids},
    ).json()["id"]
    r = client.patch(f"/api/v1/tasks/{task_id}/cancel", headers=auth(user_token))
    assert r.json()["status"] == "canceled"
