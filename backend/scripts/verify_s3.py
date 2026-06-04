"""Quick S3 connectivity check.

Usage (from backend/ with .venv active and .env filled in):
    python -m scripts.verify_s3

Uploads a tiny test object, prints a presigned URL, then deletes it.
A success here means image upload / dispatch will work against real S3.
"""

from app.core.config import get_settings
from app.services.storage import S3Storage


def main() -> None:
    s = get_settings()
    print(f"bucket={s.s3_bucket}  region={s.s3_region}  endpoint={s.s3_endpoint_url or 'AWS'}")
    if not s.aws_access_key_id:
        print("⚠️  SMARTPLACE_AWS_ACCESS_KEY_ID 가 비어 있습니다. .env 를 확인하세요.")
        return

    storage = S3Storage()
    key = "healthcheck/verify.txt"
    storage.upload(key, b"smartplace s3 ok", "text/plain")
    print("✅ 업로드 성공")
    print("presigned URL (브라우저에서 열리면 성공):")
    print(storage.presigned_url(key))
    storage.delete(key)
    print("✅ 삭제 성공 — S3 연결 정상")


if __name__ == "__main__":
    main()
