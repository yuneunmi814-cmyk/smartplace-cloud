"""Payment-provider abstraction. Swap MockProvider for LemonSqueezy / Stripe /
Toss by implementing the same interface — the rest of the app is unchanged.

For software subscriptions, LemonSqueezy is recommended (Merchant of Record:
handles VAT/refunds and has built-in license keys). The Mock here lets the whole
flow run end-to-end locally without any real provider account."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


@dataclass
class CheckoutResult:
    provider: str
    provider_subscription_id: str
    current_period_end: datetime


class BillingProvider(Protocol):
    name: str

    def start_subscription(self, *, email: str, plan: str, months: int) -> CheckoutResult:
        """Create/renew a subscription and return its current period end."""
        ...


class MockProvider:
    """Instant 'paid' subscription — no external calls. Dev/test only."""

    name = "mock"

    def start_subscription(self, *, email: str, plan: str, months: int) -> CheckoutResult:
        end = datetime.now(timezone.utc) + timedelta(days=30 * months)
        # Deterministic-ish id from email so re-subscribing is idempotent-friendly.
        sub_id = f"mock_{abs(hash((email, plan))) % 10**10:010d}"
        return CheckoutResult(provider=self.name, provider_subscription_id=sub_id, current_period_end=end)


class LemonSqueezyProvider:
    """Real provider skeleton. The subscription becomes active via webhook
    (routers/billing.py), so checkout here only needs to hand back a hosted
    checkout URL. The actual API call needs the store/variant IDs from the
    user's LemonSqueezy account — wire those before enabling.

    Kept thin and config-driven on purpose; it is not exercised by tests because
    it depends on a live account. Webhook signature/parse (the security-critical
    path) lives in app/billing/lemonsqueezy.py and *is* tested."""

    name = "lemonsqueezy"

    def start_subscription(self, *, email: str, plan: str, months: int) -> CheckoutResult:
        raise NotImplementedError(
            "LemonSqueezy 체크아웃은 호스티드 결제 URL 흐름입니다. 스토어/variant ID 설정 후 "
            "POST /v1/checkouts 를 호출해 결제 URL을 발급하고, 활성화는 webhook 으로 처리하세요."
        )


def get_provider() -> BillingProvider:
    # Single switch point. Import here to avoid a circular import at module load.
    from app.core.config import get_settings

    name = get_settings().billing_provider
    if name == "lemonsqueezy":
        return LemonSqueezyProvider()
    return MockProvider()
