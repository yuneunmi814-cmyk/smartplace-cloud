from app.worker.processor import process_task
from tests._helpers import setup_targets


def _dispatch(client, auth, token, image_id, place_ids):
    return client.post(
        "/api/v1/tasks/dispatch",
        headers=auth(token),
        json={"imageId": image_id, "placeIds": place_ids},
    ).json()["id"]


def test_worker_processes_all_success(client, user_token, auth, db, fakes):
    _, place_ids, _, image_id = setup_targets(client, auth, user_token)
    task_id = _dispatch(client, auth, user_token, image_id, place_ids)

    status = process_task(db, task_id)
    assert status == "success"

    task = client.get(f"/api/v1/tasks/{task_id}", headers=auth(user_token)).json()
    assert all(it["status"] == "ok" for it in task["items"])
    assert all(it["attempts"] == 1 for it in task["items"])
    # Gateway called once per place.
    assert len(fakes.gateway.calls) == 2


def test_worker_retries_then_marks_partial(client, user_token, auth, db, fakes):
    _, place_ids, naver_ids, image_id = setup_targets(client, auth, user_token)
    # Make the first place always fail → exhausts retries.
    fakes.gateway.fail_place_ids = {naver_ids[0]}
    task_id = _dispatch(client, auth, user_token, image_id, place_ids)

    status = process_task(db, task_id)
    assert status == "partial"

    task = client.get(f"/api/v1/tasks/{task_id}", headers=auth(user_token)).json()
    by_status = {it["status"] for it in task["items"]}
    assert by_status == {"ok", "fail"}
    failed = next(it for it in task["items"] if it["status"] == "fail")
    assert failed["attempts"] == 2  # SMARTPLACE_TASK_MAX_RETRIES


def test_worker_all_fail(client, user_token, auth, db, fakes):
    _, place_ids, naver_ids, image_id = setup_targets(client, auth, user_token)
    fakes.gateway.fail_place_ids = set(naver_ids)
    task_id = _dispatch(client, auth, user_token, image_id, place_ids)
    assert process_task(db, task_id) == "failed"
