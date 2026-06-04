"""Object storage (AWS S3). Real boto3 adapter behind a swappable interface so
tests can substitute an in-memory store."""

from __future__ import annotations

from typing import Protocol

from app.core.config import get_settings

settings = get_settings()


class Storage(Protocol):
    def upload(self, key: str, data: bytes, content_type: str) -> None: ...
    def presigned_url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


class S3Storage:
    """Real AWS S3 adapter. Credentials/region/bucket come from settings."""

    def __init__(self) -> None:
        import boto3

        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def presigned_url(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=settings.s3_url_ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


class InMemoryStorage:
    """Test/dev fallback. Holds bytes in a dict, returns fake URLs."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = data

    def presigned_url(self, key: str) -> str:
        return f"memory://{key}"

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage


def set_storage(storage: Storage | None) -> None:
    """Override the active storage (used by tests)."""
    global _storage
    _storage = storage
