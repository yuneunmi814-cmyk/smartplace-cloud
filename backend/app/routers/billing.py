"""Subscription billing. The mock ``/subscribe`` endpoint starts a paid period;
a real deployment would instead redirect to a provider checkout and let the
``/webhook`` update the subscription on payment events.

``Subscription.current_period_end`` is the single source of truth for license
expiry — see routers/license.py::_current_expiry."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing import lemonsqueezy
from app.billing.provider import get_provider
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_role
from app.models import Subscription, User
from app.schemas import SubscribeReq
from app.services import audit

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
settings = get_settings()


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    body: SubscribeReq,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
) -> dict:
    """Mock checkout: marks the user's subscription active for N months.

    Admin-only because the Mock provider charges nothing — in production this is
    replaced by a customer-facing checkout + webhook."""
    user = db.scalar(select(User).where(User.email == body.email))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 이메일의 사용자가 없습니다.")

    result = get_provider().start_subscription(email=body.email, plan=body.plan, months=body.months)
    sub = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.id.desc())
    )
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)
    sub.provider = result.provider
    sub.provider_subscription_id = result.provider_subscription_id
    sub.plan = body.plan
    sub.status = "active"
    sub.current_period_end = result.current_period_end
    db.commit()
    db.refresh(sub)

    audit.record(
        db,
        actor_user_id=admin.id,
        action="billing.subscribe",
        target_type="subscription",
        target_id=sub.id,
        detail={"email": body.email, "plan": body.plan, "months": body.months},
    )
    return {
        "status": sub.status,
        "plan": sub.plan,
        "currentPeriodEnd": sub.current_period_end,
        "provider": sub.provider,
    }


def _normalize(raw: bytes) -> tuple[dict, str | None]:
    """Parse the webhook body into our normalized event + an event-type label.

    Tries the LemonSqueezy shape first, then the generic provider-agnostic shape
    {"type", "providerSubscriptionId", "status", "currentPeriodEnd"}."""
    payload = json.loads(raw)
    ls = lemonsqueezy.parse_event(payload)
    if ls is not None:
        return ls, payload.get("meta", {}).get("event_name")
    cpe = payload.get("currentPeriodEnd")
    generic = {
        "providerSubscriptionId": payload.get("providerSubscriptionId"),
        "status": payload.get("status"),
        "currentPeriodEnd": (
            datetime.fromisoformat(cpe).astimezone(timezone.utc) if cpe else None
        ),
        "email": payload.get("email"),
        "plan": payload.get("plan"),
    }
    return generic, payload.get("type")


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Provider webhook. When ``lemonsqueezy_webhook_secret`` is configured, the
    ``X-Signature`` header is verified against the RAW body (HMAC-SHA256) before
    the payload is trusted — otherwise anyone could POST a fake renewal.

    Locates the subscription by provider id, falling back to the user's email
    (LemonSqueezy ``subscription_created`` arrives before we know the id)."""
    raw = await request.body()
    secret = settings.lemonsqueezy_webhook_secret
    if secret and not lemonsqueezy.verify_signature(raw, request.headers.get("X-Signature"), secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "웹훅 서명 검증 실패")

    try:
        event, event_type = _normalize(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "잘못된 웹훅 본문") from exc

    sub_id = event.get("providerSubscriptionId")
    email = event.get("email")
    sub = None
    if sub_id:
        sub = db.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == sub_id)
        )
    if sub is None and email:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "구독 대상 사용자를 찾을 수 없습니다.")
        sub = db.scalar(
            select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.id.desc())
        )
        if sub is None:
            # Seed period end so a created-event without renews_at can't violate
            # NOT NULL; a real event overrides it below.
            sub = Subscription(user_id=user.id, current_period_end=datetime.now(timezone.utc))
            db.add(sub)
        sub.provider = settings.billing_provider
        if sub_id:
            sub.provider_subscription_id = sub_id
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "구독을 찾을 수 없습니다.")

    if event.get("status") in {"active", "canceled", "past_due"}:
        sub.status = event["status"]
    if event.get("plan"):
        sub.plan = event["plan"]
    if event.get("currentPeriodEnd"):
        sub.current_period_end = event["currentPeriodEnd"]
    db.commit()
    audit.record(
        db,
        actor_user_id=sub.user_id,
        action="billing.webhook",
        target_type="subscription",
        target_id=sub.id,
        detail={"type": event_type, "status": sub.status},
    )
    return {"ok": True, "status": sub.status}
