"""LemonSqueezy adapter: webhook signature verification + event normalization.

LemonSqueezy is a Merchant of Record (handles VAT/refunds) with built-in
subscriptions — recommended for software sales. This module covers the two
verifiable, security-critical pieces:

  * verify_signature() — HMAC-SHA256 of the RAW request body against the webhook
    signing secret (constant-time compare). The single thing that makes a
    webhook trustworthy.
  * parse_event()      — map LemonSqueezy's payload onto our normalized shape.

Creating checkouts (the outbound API call) needs the store/variant IDs from the
user's LemonSqueezy account, so that lives in LemonSqueezyProvider as a thin,
config-driven call and is intentionally not exercised by tests here.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

# LemonSqueezy subscription status -> our Subscription.status
_STATUS_MAP = {
    "active": "active",
    "on_trial": "active",
    "paused": "past_due",
    "past_due": "past_due",
    "unpaid": "canceled",
    "cancelled": "canceled",  # won't renew (still usable until ends_at — see expiry below)
    "expired": "canceled",
}


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """True iff ``signature`` (hex) == HMAC-SHA256(secret, raw_body). Constant-time."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def parse_event(payload: dict) -> dict | None:
    """Normalize a LemonSqueezy webhook payload. Returns None if it isn't one
    (so the caller can fall back to the generic shape).

    Normalized keys: providerSubscriptionId, status, currentPeriodEnd (datetime
    or None), email, plan."""
    meta = payload.get("meta")
    data = payload.get("data")
    if not isinstance(meta, dict) or not isinstance(data, dict):
        return None
    if "event_name" not in meta or data.get("type") != "subscriptions":
        return None

    attrs = data.get("attributes", {}) or {}
    ls_status = attrs.get("status", "")
    # Active-but-cancelled subscriptions stay usable until ends_at; otherwise the
    # next renewal date is the period end.
    period_end = attrs.get("ends_at") if ls_status == "cancelled" else attrs.get("renews_at")
    return {
        "providerSubscriptionId": str(data.get("id")) if data.get("id") is not None else None,
        "status": _STATUS_MAP.get(ls_status, "past_due"),
        "currentPeriodEnd": _parse_dt(period_end),
        "email": attrs.get("user_email"),
        "plan": attrs.get("variant_name"),
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    # LemonSqueezy emits ISO-8601, often with a trailing 'Z'.
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
