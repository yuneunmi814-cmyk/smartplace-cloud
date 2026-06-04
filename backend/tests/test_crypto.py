from app.core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    secret = "naver-session-token-XYZ"
    blob = encrypt(secret)
    assert blob != secret
    assert decrypt(blob) == secret


def test_ciphertext_is_nondeterministic():
    # Random nonce → same plaintext encrypts to different ciphertexts.
    assert encrypt("same") != encrypt("same")
