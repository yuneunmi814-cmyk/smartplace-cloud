"""Naver API gateway client. Real HTTP adapter behind a swappable interface.

A single call does ONE apply attempt; retry/backoff is the worker's job
(see app/worker/worker.py) per the design's emphasis on a robust Retry Policy.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import get_settings

settings = get_settings()


class GatewayError(Exception):
    """Raised when the gateway rejects or fails an apply request."""


class NaverGateway(Protocol):
    def apply_main_image(self, account_token: str, place_id: str, image_url: str) -> None: ...


class HttpNaverGateway:
    """Real gateway adapter. Posts the image URL to the configured gateway."""

    def apply_main_image(self, account_token: str, place_id: str, image_url: str) -> None:
        import httpx

        try:
            resp = httpx.post(
                f"{settings.naver_gateway_url}/places/{place_id}/main-image",
                headers={
                    "Authorization": f"Bearer {settings.naver_gateway_key or ''}",
                    "X-Naver-Account-Token": account_token,
                },
                json={"imageUrl": image_url},
                timeout=settings.naver_request_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise GatewayError(f"gateway transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise GatewayError(f"gateway returned {resp.status_code}: {resp.text[:200]}")


class FakeNaverGateway:
    """Test/dev gateway. Records calls and can be told to fail."""

    def __init__(self, fail_place_ids: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_place_ids = fail_place_ids or set()

    def apply_main_image(self, account_token: str, place_id: str, image_url: str) -> None:
        self.calls.append((place_id, image_url))
        if place_id in self.fail_place_ids:
            raise GatewayError(f"simulated failure for place {place_id}")


_gateway: NaverGateway | None = None


def get_gateway() -> NaverGateway:
    global _gateway
    if _gateway is None:
        _gateway = HttpNaverGateway()
    return _gateway


def set_gateway(gateway: NaverGateway | None) -> None:
    """Override the active gateway (used by tests)."""
    global _gateway
    _gateway = gateway
