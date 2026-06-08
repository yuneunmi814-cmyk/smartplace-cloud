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


def get_provider() -> BillingProvider:
    # Single switch point; later read settings.billing_provider and branch here.
    return MockProvider()
