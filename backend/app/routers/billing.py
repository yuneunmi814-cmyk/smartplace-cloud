"""Subscription billing. The mock ``/subscribe`` endpoint starts a paid period;
a real deployment would instead redirect to a provider checkout and let the
``/webhook`` update the subscription on payment events.

``Subscription.current_period_end`` is the single source of truth for license
expiry — see routers/license.py::_current_expiry."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.provider import get_provider
from app.core.database import get_db
from app.core.security import require_role
from app.models import Subscription, User
from app.schemas import SubscribeReq
from app.services import audit

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


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


@router.post("/webhook")
def webhook(event: dict, db: Session = Depends(get_db)) -> dict:
    """Provider webhook stub. Maps ``subscription.*`` events to our row.

    Expected shape (provider-agnostic): {"type": "subscription.updated",
    "providerSubscriptionId": "...", "status": "active|canceled|past_due",
    "currentPeriodEnd": "<iso8601>"}.

    NOTE: a production handler MUST verify the provider's signature header before
    trusting the body. Left out here on purpose (no real provider wired)."""
    sub_id = event.get("providerSubscriptionId")
    if not sub_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "providerSubscriptionId 누락")
    sub = db.scalar(
        select(Subscription).where(Subscription.provider_subscription_id == sub_id)
    )
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "구독을 찾을 수 없습니다.")

    new_status = event.get("status")
    if new_status in {"active", "canceled", "past_due"}:
        sub.status = new_status
    cpe = event.get("currentPeriodEnd")
    if cpe:
        sub.current_period_end = datetime.fromisoformat(cpe).astimezone(timezone.utc)
    db.commit()
    audit.record(
        db,
        actor_user_id=sub.user_id,
        action="billing.webhook",
        target_type="subscription",
        target_id=sub.id,
        detail={"type": event.get("type"), "status": sub.status},
    )
    return {"ok": True, "status": sub.status}
