from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All values come from env (prefix SMARTPLACE_)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SMARTPLACE_", extra="ignore")

    # --- Database ---
    # SQLite for local dev/test; set to Postgres in prod / docker-compose.
    database_url: str = "sqlite:///./smartplace_cloud.db"

    # --- Auth (JWT) ---
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    # --- Encryption ---
    # 32-byte key (base64 or hex) for AES-256-GCM of Naver tokens. CHANGE in prod.
    # Default is a dev-only fixed key; generate with: secrets.token_hex(32)
    data_encryption_key: str = "0" * 64  # 64 hex chars = 32 bytes

    # --- Dispatch mode ---
    # inline_dispatch=True processes tasks in-process (FastAPI BackgroundTasks),
    # no Redis/worker needed — handy for local/single-user setups.
    inline_dispatch: bool = False

    # --- Redis task queue ---
    redis_url: str = "redis://localhost:6379/0"
    task_queue_name: str = "smartplace:tasks"
    # Retry policy for worker dispatch (senior advice: robust retries).
    task_max_retries: int = 3
    task_retry_backoff_seconds: int = 5

    # --- AWS S3 ---
    s3_bucket: str = "smartplace-images"
    s3_region: str = "ap-northeast-2"
    # Optional custom endpoint (e.g. MinIO). Leave empty for real AWS.
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    # Presigned URL TTL.
    s3_url_ttl_seconds: int = 3600

    # --- Naver gateway ---
    naver_gateway_url: str = "http://localhost:8100"
    naver_gateway_key: str | None = "gateway-key-change-me"
    # Each apply drives a real browser; give it room.
    naver_request_timeout_seconds: int = 180

    cors_origins: list[str] = ["http://localhost:5173"]

    # --- License signing (Ed25519) ---
    # Private key (hex, 32 bytes) signs offline license files; keep it ONLY on
    # the server. Public counterpart is baked into desktop/license.py.
    # DEV DEFAULT below is a throwaway pair — regenerate for prod with
    #   python -m scripts.gen_license_keys
    # and set SMARTPLACE_LICENSE_PRIVATE_KEY in .env (never commit the real one).
    license_private_key: str = (
        "cd8b149dce67c9d01907962da78eb683371bb4ba3c75b51da6e533236313ee09"
    )
    # Matching public key — used server-side only for self-test/verification.
    license_public_key: str = (
        "82b12111ef3ff4f69260f17829ab190e0a1a49aafe642f9af506e314d90862ee"
    )
    # New licenses default to this many days when no subscription is attached.
    license_default_days: int = 365


@lru_cache
def get_settings() -> Settings:
    return Settings()
