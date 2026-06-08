"""License signing + offline verification + activation flow."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.services.license_file import issue_license_file, verify_license_file

settings = get_settings()
PRIV = settings.license_private_key
PUB = settings.license_public_key


def _issue(**over):
    kw = dict(
        license_key="SPC-TEST",
        plan="basic",
        device_fingerprint="fp-abcdef123456",
        expiry=datetime.now(timezone.utc) + timedelta(days=30),
        seats=1,
    )
    kw.update(over)
    return issue_license_file(PRIV, **kw)


# ---- unit: sign / verify ---------------------------------------------------
def test_roundtrip_ok():
    lf = _issue()
    p = verify_license_file(lf, PUB, device_fingerprint="fp-abcdef123456")
    assert p["licenseKey"] == "SPC-TEST"
    assert p["plan"] == "basic"


def test_tampered_payload_fails():
    lf = _issue()
    # Flip a character inside the envelope → signature must fail.
    bad = lf.replace("LICENSE FILE-----\n", "LICENSE FILE-----\nA", 1)
    with pytest.raises(ValueError, match="형식|서명"):
        verify_license_file(bad, PUB, device_fingerprint="fp-abcdef123456")


def test_wrong_device_fails():
    lf = _issue()
    with pytest.raises(ValueError, match="다른 기기"):
        verify_license_file(lf, PUB, device_fingerprint="fp-someoneelse")


def test_expired_fails():
    lf = _issue(expiry=datetime.now(timezone.utc) - timedelta(days=1))
    with pytest.raises(ValueError, match="만료"):
        verify_license_file(lf, PUB, device_fingerprint="fp-abcdef123456")


def test_wrong_public_key_fails():
    lf = _issue()
    other_pub = "00" * 32
    with pytest.raises(ValueError, match="서명 검증 실패"):
        verify_license_file(lf, other_pub, device_fingerprint="fp-abcdef123456")


# ---- integration: issue → activate ----------------------------------------
def test_admin_issue_and_activate(client, admin_token, auth):
    client.post("/api/v1/auth/signup", json={"email": "cust@example.com", "password": "password123"})
    r = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "cust@example.com", "plan": "pro", "seats": 2, "days": 10},
    )
    assert r.status_code == 201, r.text
    key = r.json()["licenseKey"]
    assert key.startswith("SPC-")

    act = client.post(
        "/api/v1/license/activate",
        json={"licenseKey": key, "deviceFingerprint": "device-fingerprint-1", "deviceName": "PC1"},
    )
    assert act.status_code == 200, act.text
    lf = act.json()["licenseFile"]
    p = verify_license_file(lf, PUB, device_fingerprint="device-fingerprint-1")
    assert p["plan"] == "pro"
    assert p["seats"] == 2


def test_activate_unknown_key_rejected(client):
    r = client.post(
        "/api/v1/license/activate",
        json={"licenseKey": "SPC-DOES-NOT-EXIST", "deviceFingerprint": "device-fingerprint-1"},
    )
    assert r.status_code == 403


def test_seat_limit_enforced(client, admin_token, auth):
    client.post("/api/v1/auth/signup", json={"email": "seat@example.com", "password": "password123"})
    key = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "seat@example.com", "plan": "basic", "seats": 1},
    ).json()["licenseKey"]

    a = client.post("/api/v1/license/activate",
                    json={"licenseKey": key, "deviceFingerprint": "fingerprint-aaaa"})
    assert a.status_code == 200
    # Same device re-activates fine (no new seat consumed).
    again = client.post("/api/v1/license/activate",
                        json={"licenseKey": key, "deviceFingerprint": "fingerprint-aaaa"})
    assert again.status_code == 200
    # A second distinct device exceeds the single seat.
    b = client.post("/api/v1/license/activate",
                    json={"licenseKey": key, "deviceFingerprint": "fingerprint-bbbb"})
    assert b.status_code == 409


def test_list_mine_and_deactivate_frees_seat(client, admin_token, user_token, auth):
    # Admin issues a 1-seat license to the regular user.
    key = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "user@example.com", "plan": "basic", "seats": 1},
    ).json()["licenseKey"]
    client.post("/api/v1/license/activate",
                json={"licenseKey": key, "deviceFingerprint": "fingerprint-dev1", "deviceName": "Old PC"})

    # Owner sees the license + its one device.
    mine = client.get("/api/v1/license/mine", headers=auth(user_token)).json()
    assert len(mine) == 1
    lic = mine[0]
    assert len(lic["devices"]) == 1
    dev_id = lic["devices"][0]["id"]

    # Seat is full → a second device is rejected.
    assert client.post("/api/v1/license/activate",
                       json={"licenseKey": key, "deviceFingerprint": "fingerprint-dev2"}).status_code == 409

    # Owner deactivates the old device → seat freed → new device activates.
    d = client.delete(f"/api/v1/license/{lic['id']}/devices/{dev_id}", headers=auth(user_token))
    assert d.status_code == 204
    assert client.post("/api/v1/license/activate",
                       json={"licenseKey": key, "deviceFingerprint": "fingerprint-dev2"}).status_code == 200


def test_deactivate_requires_ownership(client, admin_token, user_token, auth):
    # License belongs to admin; the regular user must not touch its devices.
    key = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "admin@example.com", "plan": "basic", "seats": 1},
    ).json()
    lid = key["id"]
    client.post("/api/v1/license/activate",
                json={"licenseKey": key["licenseKey"], "deviceFingerprint": "fingerprint-adm1"})
    devs = client.get("/api/v1/license/mine", headers=auth(admin_token)).json()[0]["devices"]
    r = client.delete(f"/api/v1/license/{lid}/devices/{devs[0]['id']}", headers=auth(user_token))
    assert r.status_code == 403


def test_revoke_blocks_activation(client, admin_token, auth):
    created = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "admin@example.com", "plan": "basic", "seats": 1},
    ).json()
    r = client.post(f"/api/v1/license/{created['id']}/revoke", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"
    act = client.post("/api/v1/license/activate",
                      json={"licenseKey": created["licenseKey"], "deviceFingerprint": "fingerprint-x"})
    assert act.status_code == 403


def test_subscription_drives_expiry(client, admin_token, auth):
    client.post("/api/v1/auth/signup", json={"email": "sub@example.com", "password": "password123"})
    key = client.post(
        "/api/v1/license",
        headers=auth(admin_token),
        json={"email": "sub@example.com", "plan": "basic", "seats": 1, "days": 5},
    ).json()["licenseKey"]

    # Start a 3-month subscription → activation expiry should jump well past 5 days.
    client.post("/api/v1/billing/subscribe", headers=auth(admin_token),
                json={"email": "sub@example.com", "plan": "basic", "months": 3})
    act = client.post("/api/v1/license/activate",
                      json={"licenseKey": key, "deviceFingerprint": "fingerprint-sub1"})
    expiry = datetime.fromisoformat(act.json()["expiry"])
    if expiry.tzinfo is None:  # SQLite drops tzinfo; treat stored value as UTC
        expiry = expiry.replace(tzinfo=timezone.utc)
    assert expiry > datetime.now(timezone.utc) + timedelta(days=60)
    # And the signed file's expiry must reflect the subscription, not the 5-day fallback.
    p = verify_license_file(act.json()["licenseFile"], PUB, device_fingerprint="fingerprint-sub1")
    assert datetime.fromisoformat(p["expiry"]) > datetime.now(timezone.utc) + timedelta(days=60)
