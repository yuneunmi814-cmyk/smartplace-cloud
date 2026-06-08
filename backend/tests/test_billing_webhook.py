"""Webhook signature verification + LemonSqueezy event mapping."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

from app.billing import lemonsqueezy as ls
from app.core.config import get_settings

settings = get_settings()


# ---- unit: signature -------------------------------------------------------
def test_verify_signature_roundtrip():
    secret = "whsec_test"
    body = b'{"hello":"world"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert ls.verify_signature(body, sig, secret) is True
    assert ls.verify_signature(body, sig, "wrong-secret") is False
    assert ls.verify_signature(body + b"x", sig, secret) is False  # tampered body
    assert ls.verify_signature(body, None, secret) is False


# ---- unit: event parsing ---------------------------------------------------
def _ls_event(status="active", renews_at="2030-01-01T00:00:00Z", ends_at=None, email="x@e.com"):
    return {
        "meta": {"event_name": "subscription_updated"},
        "data": {
            "type": "subscriptions",
            "id": "999",
            "attributes": {
                "status": status,
                "renews_at": renews_at,
                "ends_at": ends_at,
                "user_email": email,
                "variant_name": "Pro",
            },
        },
    }


def test_parse_active_uses_renews_at():
    n = ls.parse_event(_ls_event())
    assert n["providerSubscriptionId"] == "999"
    assert n["status"] == "active"
    assert n["plan"] == "Pro"
    assert n["currentPeriodEnd"] == datetime(2030, 1, 1, tzinfo=timezone.utc)


def test_parse_cancelled_uses_ends_at():
    n = ls.parse_event(_ls_event(status="cancelled", ends_at="2031-06-01T00:00:00Z"))
    assert n["status"] == "canceled"
    assert n["currentPeriodEnd"] == datetime(2031, 6, 1, tzinfo=timezone.utc)


def test_parse_non_lemonsqueezy_returns_none():
    assert ls.parse_event({"type": "subscription.updated", "providerSubscriptionId": "1"}) is None


# ---- integration: webhook endpoint ----------------------------------------
def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    body = json.dumps(_ls_event()).encode()
    r = client.post("/api/v1/billing/webhook", content=body,
                    headers={"X-Signature": "deadbeef", "Content-Type": "application/json"})
    assert r.status_code == 401


def test_webhook_creates_and_updates_subscription(client, admin_token, auth, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    client.post("/api/v1/auth/signup", json={"email": "buyer@e.com", "password": "password123"})

    body = json.dumps(_ls_event(email="buyer@e.com")).encode()
    r = client.post("/api/v1/billing/webhook", content=body,
                    headers={"X-Signature": _sign(body, "whsec_test")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    # The new subscription must now drive a license's expiry to 2030.
    key = client.post("/api/v1/license", headers=auth(admin_token),
                      json={"email": "buyer@e.com", "plan": "basic", "seats": 1, "days": 3}).json()["licenseKey"]
    act = client.post("/api/v1/license/activate",
                      json={"licenseKey": key, "deviceFingerprint": "fingerprint-buyer1"})
    expiry = datetime.fromisoformat(act.json()["expiry"])
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    assert expiry.year == 2030


def test_webhook_generic_shape_still_works(client, admin_token, auth):
    # No secret configured → signature not required; generic provider shape.
    client.post("/api/v1/auth/signup", json={"email": "g@e.com", "password": "password123"})
    client.post("/api/v1/billing/subscribe", headers=auth(admin_token),
                json={"email": "g@e.com", "plan": "basic", "months": 1})
    # Grab the mock sub id via a renewal webhook keyed by email.
    body = json.dumps({
        "type": "subscription.updated", "email": "g@e.com",
        "status": "canceled", "currentPeriodEnd": "2029-01-01T00:00:00+00:00",
    }).encode()
    r = client.post("/api/v1/billing/webhook", content=body)
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"
