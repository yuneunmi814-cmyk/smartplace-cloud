"""Signed, offline-verifiable license files (Keygen-style).

The cloud signs a license payload with an **Ed25519 private key**; the desktop
app verifies it with the **public key** only. The private key never leaves the
server, so even a fully reverse-engineered app cannot forge a license.

Envelope format (mirrors Keygen's `-----BEGIN MACHINE FILE-----`):

    -----BEGIN LICENSE FILE-----
    base64(json({"data": <data_b64>, "sig": <sig_b64>, "alg": "ed25519"}))
    -----END LICENSE FILE-----

where ``data_b64 = base64(json(payload))`` and the signature is computed over
``SIGN_PREFIX + data_b64`` (the *encoded* string, not the decoded JSON — this
is the single most common verification bug, so keep it exact on both sides).
"""

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Signing-message prefix. MUST be byte-for-byte identical on the verify side
# (desktop/license.py). A 1-byte mismatch makes every verification fail.
SIGN_PREFIX = b"license/"

_BEGIN = "-----BEGIN LICENSE FILE-----"
_END = "-----END LICENSE FILE-----"


def issue_license_file(
    priv_hex: str,
    *,
    license_key: str,
    plan: str,
    device_fingerprint: str,
    expiry: datetime,
    seats: int,
) -> str:
    """Sign a license payload and wrap it in the BEGIN/END envelope."""
    # A naive expiry (e.g. read back from SQLite, which drops tzinfo) is meant as
    # UTC — attach UTC rather than letting astimezone() assume local time.
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    payload = {
        "licenseKey": license_key,
        "plan": plan,
        "deviceFingerprint": device_fingerprint,
        "issued": datetime.now(timezone.utc).isoformat(),
        "expiry": expiry.astimezone(timezone.utc).isoformat(),
        "seats": seats,
    }
    data_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    sig_b64 = base64.b64encode(priv.sign(SIGN_PREFIX + data_b64.encode())).decode()
    envelope = base64.b64encode(
        json.dumps({"data": data_b64, "sig": sig_b64, "alg": "ed25519"}).encode()
    ).decode()
    return f"{_BEGIN}\n{envelope}\n{_END}"


def verify_license_file(
    license_file: str,
    public_key_hex: str,
    *,
    device_fingerprint: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Verify signature + expiry (and optionally device binding). Returns the
    decoded payload, or raises ``ValueError`` with a user-facing reason.

    Shared with the desktop client logic; the desktop ships its own copy with
    the public key baked in, but the algorithm here is the source of truth.
    """
    now = now or datetime.now(timezone.utc)
    body = license_file.replace(_BEGIN, "").replace(_END, "").strip()
    try:
        env = json.loads(base64.b64decode(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("라이선스 파일 형식이 올바르지 않습니다") from exc
    if env.get("alg") != "ed25519":
        raise ValueError("지원하지 않는 서명 알고리즘")
    data_b64, sig_b64 = env["data"], env["sig"]

    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    try:
        pub.verify(base64.b64decode(sig_b64), SIGN_PREFIX + data_b64.encode())
    except InvalidSignature as exc:
        raise ValueError("서명 검증 실패 — 위변조된 라이선스") from exc

    p = json.loads(base64.b64decode(data_b64))
    if device_fingerprint is not None and p["deviceFingerprint"] != device_fingerprint:
        raise ValueError("다른 기기에서 발급된 라이선스입니다")
    if datetime.fromisoformat(p["issued"]) > now:
        raise ValueError("발급일이 미래입니다 — 시스템 시계를 확인하세요")
    if datetime.fromisoformat(p["expiry"]) < now:
        raise ValueError("구독이 만료되었습니다")
    return p
