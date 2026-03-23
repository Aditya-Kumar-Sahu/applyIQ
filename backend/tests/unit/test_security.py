from __future__ import annotations

from app.core.security import EncryptionService, get_password_hash, verify_password


def test_password_hash_round_trip() -> None:
    password = "SuperSecret123!"
    password_hash = get_password_hash(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_encryption_service_encrypts_and_decrypts_per_user() -> None:
    service = EncryptionService(
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
    )

    ciphertext = service.encrypt_for_user("user-123", "hunter2@example.com")

    assert ciphertext != "hunter2@example.com"
    assert service.decrypt_for_user("user-123", ciphertext) == "hunter2@example.com"
