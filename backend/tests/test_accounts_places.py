from sqlalchemy import select

from app.models import NaverAccount


def _link(client, auth, token, alias="가맹점주A", secret="super-secret-token"):
    return client.post(
        "/api/v1/naver-accounts", headers=auth(token), json={"alias": alias, "token": secret}
    )


def test_link_account_encrypts_token(client, user_token, auth, db):
    r = _link(client, auth, user_token, secret="plain-naver-token")
    assert r.status_code == 201
    assert "token" not in r.json()  # plaintext never returned

    stored = db.scalar(select(NaverAccount)).encrypted_token
    assert stored != "plain-naver-token"  # encrypted at rest


def test_list_accounts(client, user_token, auth):
    _link(client, auth, user_token, alias="A")
    _link(client, auth, user_token, alias="B")
    rows = client.get("/api/v1/naver-accounts", headers=auth(user_token)).json()
    assert {a["alias"] for a in rows} == {"A", "B"}


def test_create_and_list_places(client, user_token, auth):
    account_id = _link(client, auth, user_token).json()["id"]
    client.post(
        "/api/v1/places",
        headers=auth(user_token),
        json={"accountId": account_id, "placeId": "12345", "businessName": "강남점"},
    )
    places = client.get("/api/v1/places", headers=auth(user_token)).json()
    assert len(places) == 1
    assert places[0]["businessName"] == "강남점"


def test_cannot_use_other_users_account(client, user_token, admin_token, auth):
    # admin links its own account; the normal user must not register places on it.
    admin_account = _link(client, auth, admin_token, alias="admin-acct").json()["id"]
    r = client.post(
        "/api/v1/places",
        headers=auth(user_token),
        json={"accountId": admin_account, "placeId": "999", "businessName": "x"},
    )
    assert r.status_code == 404
