from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Any

from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext


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
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, *, secret_key: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[algorithm])


class EncryptionService:
    def __init__(self, *, fernet_secret_key: str, encryption_pepper: str) -> None:
        self._fernet_secret_key = fernet_secret_key
        self._encryption_pepper = encryption_pepper

    def _build_fernet(self, user_id: str) -> Fernet:
        digest = hmac.new(
            self._encryption_pepper.encode("utf-8"),
            msg=f"{self._fernet_secret_key}:{user_id}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        derived_key = base64.urlsafe_b64encode(digest)
        return Fernet(derived_key)

    def encrypt_for_user(self, user_id: str, value: str) -> str:
        return self._build_fernet(user_id).encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_for_user(self, user_id: str, value: str) -> str:
        return self._build_fernet(user_id).decrypt(value.encode("utf-8")).decode("utf-8")
