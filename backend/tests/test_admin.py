def test_non_admin_forbidden(client, user_token, auth):
    assert client.get("/api/v1/admin/users", headers=auth(user_token)).status_code == 403


def test_set_role(client, admin_token, user_token, auth):
    users = client.get("/api/v1/admin/users", headers=auth(admin_token)).json()
    uid = next(u["id"] for u in users if u["email"] == "user@example.com")
    r = client.patch(
        f"/api/v1/admin/users/{uid}/role", headers=auth(admin_token), json={"role": "admin"}
    )
    assert r.json()["ok"] is True


def test_audit_trail_records_actions(client, user_token, auth, admin_token):
    # user_token fixture already triggered signup/approve; linking adds more.
    client.post("/api/v1/naver-accounts", headers=auth(user_token), json={"alias": "a", "token": "t"})
    logs = client.get("/api/v1/admin/audit", headers=auth(admin_token)).json()
    actions = {row["action"] for row in logs}
    assert "naver_account.link" in actions
    assert "user.approve" in actions


def test_stats(client, admin_token, auth):
    stats = client.get("/api/v1/admin/stats", headers=auth(admin_token)).json()
    assert "successRate" in stats
    assert stats["users"] >= 1
