from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet
import bcrypt
from passlib.context import CryptContext

# Fix for passlib/bcrypt incompatibility in newer versions (Python 3.12+)
if not hasattr(bcrypt, "__about__"):
    print("DEBUG: Patching bcrypt.__about__ for passlib compatibility")
    class About:
        __version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = About()

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return PASSWORD_CONTEXT.verify(plain_password, hashed_password)


def create_token(
    *,
    subject: str,
    token_type: str,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    import uuid

    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, *, secret_key: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[algorithm])


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class EncryptionService:
    def __init__(self, *, fernet_secret_key: str, encryption_pepper: str) -> None:
        self._fernet_secret_key = fernet_secret_key
        self._encryption_pepper = encryption_pepper

    def _build_fernet(self, user_id: str) -> Fernet:
        digest = hmac.new(
            self._encryption_pepper.encode("utf-8"),
            msg=f"{self._fernet_secret_key}:{user_id}".encode(),
            digestmod=hashlib.sha256,
        ).digest()
        derived_key = base64.urlsafe_b64encode(digest)
        return Fernet(derived_key)

    def encrypt_for_user(self, user_id: str, value: str) -> str:
        return self._build_fernet(user_id).encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_for_user(self, user_id: str, value: str) -> str:
        return self._build_fernet(user_id).decrypt(value.encode("utf-8")).decode("utf-8")
