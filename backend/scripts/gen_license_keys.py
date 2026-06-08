"""Generate a fresh Ed25519 keypair for license signing.

    python -m scripts.gen_license_keys

- Put the PRIVATE key in the server only (env SMARTPLACE_LICENSE_PRIVATE_KEY,
  or a secret manager). NEVER commit it.
- Put the PUBLIC key into desktop/license.py (PUBLIC_KEY_HEX) — safe to ship,
  it can only verify, not forge.
"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def main() -> None:
    priv = Ed25519PrivateKey.generate()
    priv_hex = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    print("# 서버 .env 에만 (절대 커밋 금지):")
    print(f"SMARTPLACE_LICENSE_PRIVATE_KEY={priv_hex}")
    print()
    print("# desktop/license.py 의 PUBLIC_KEY_HEX 에 박기 (배포 안전):")
    print(f"PUBLIC_KEY_HEX = \"{pub_hex}\"")


if __name__ == "__main__":
    main()
