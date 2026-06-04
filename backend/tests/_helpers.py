"""Shared setup helpers for task/worker tests."""


def setup_targets(client, auth, token, place_count=2):
    """Links an account, registers N places, uploads an image. Returns ids."""
    account_id = client.post(
        "/api/v1/naver-accounts", headers=auth(token), json={"alias": "acct", "token": "tok"}
    ).json()["id"]

    place_ids = []
    naver_ids = []
    for i in range(place_count):
        naver_id = f"100{i}"
        pid = client.post(
            "/api/v1/places",
            headers=auth(token),
            json={"accountId": account_id, "placeId": naver_id, "businessName": f"store{i}"},
        ).json()["id"]
        place_ids.append(pid)
        naver_ids.append(naver_id)

    image_id = client.post(
        "/api/v1/images/upload",
        headers=auth(token),
        files={"file": ("a.png", b"bytes", "image/png")},
    ).json()["id"]

    return account_id, place_ids, naver_ids, image_id
