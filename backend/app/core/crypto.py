"""AES-256-GCM encryption for sensitive fields (Naver tokens).

The ciphertext stored in the DB is: base64( nonce(12) || ciphertext || tag ).
The key comes from settings.data_encryption_key (32 bytes as hex or raw).
"""

import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

settings = get_settings()
_NONCE_BYTES = 12


def _load_key() -> bytes:
    raw = settings.data_encryption_key
    # Accept 64-char hex (32 bytes) or a raw 32-char string.
    try:
        key = bytes.fromhex(raw)
        if len(key) == 32:
            return key
    except ValueError:
        pass
    key = raw.encode("utf-8")
    if len(key) != 32:
        raise ValueError("data_encryption_key must decode to exactly 32 bytes (AES-256)")
    return key


def encrypt(plaintext: str) -> str:
    aesgcm = AESGCM(_load_key())
    import os

    nonce = os.urandom(_NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str) -> str:
    blob = base64.b64decode(token)
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    aesgcm = AESGCM(_load_key())
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
