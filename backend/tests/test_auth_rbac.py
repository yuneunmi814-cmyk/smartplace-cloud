def test_first_signup_becomes_admin(client):
    r = client.post(
        "/api/v1/auth/signup", json={"email": "admin@example.com", "password": "password123"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "admin"
    assert body["status"] == "approved"


def test_second_signup_is_pending(client, admin_token):
    r = client.post(
        "/api/v1/auth/signup", json={"email": "u2@example.com", "password": "password123"}
    )
    assert r.json()["status"] == "pending"


def test_pending_user_blocked_then_allowed(client, admin_token, auth):
    client.post("/api/v1/auth/signup", json={"email": "p@example.com", "password": "password123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": "p@example.com", "password": "password123"}
    ).json()["accessToken"]

    # Pending → blocked from linking accounts.
    blocked = client.post(
        "/api/v1/naver-accounts", headers=auth(token), json={"alias": "a", "token": "t"}
    )
    assert blocked.status_code == 403

    # Approve, then allowed.
    users = client.get("/api/v1/admin/users", headers=auth(admin_token)).json()
    uid = next(u["id"] for u in users if u["email"] == "p@example.com")
    client.post(f"/api/v1/admin/users/{uid}/approve", headers=auth(admin_token))
    ok = client.post(
        "/api/v1/naver-accounts", headers=auth(token), json={"alias": "a", "token": "t"}
    )
    assert ok.status_code == 201


def test_me_endpoint(client, admin_token, auth):
    r = client.get("/api/v1/auth/me", headers=auth(admin_token))
    assert r.json()["email"] == "admin@example.com"
