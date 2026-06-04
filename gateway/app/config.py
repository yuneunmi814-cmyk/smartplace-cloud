from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gateway configuration (prefix GATEWAY_)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_", extra="ignore")

    # Shared secret the caller (worker) must present as `Authorization: Bearer`.
    # env var: GATEWAY_KEY
    key: str = "gateway-key-change-me"

    # MOCK mode: skip Playwright entirely and return success. Used for wiring
    # tests and CI. Set GATEWAY_MOCK=0 to run real automation.
    mock: bool = True

    # Real-automation knobs.
    headless: bool = True
    naver_login_url: str = "https://nid.naver.com/nidlogin.login"
    smartplace_url: str = "https://new.smartplace.naver.com"
    # The 대표이미지 (main photo) is managed in the Naver Booking partner center.
    booking_partner_url: str = "https://partner.booking.naver.com"
    action_timeout_ms: int = 20000
    login_timeout_ms: int = 180000
    # Reuse a seeded login session for this many seconds (default 6h).
    session_ttl_seconds: int = 21600
    # Auto ID/PW login is OFF by default — it triggers captcha/2FA/security
    # modules. Prefer manual session seeding (python -m app.seed_session).
    allow_password_login: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
