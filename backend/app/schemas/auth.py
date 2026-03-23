from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class DeleteAccountRequest(BaseModel):
    password_confirmation: str = Field(min_length=8)


class AuthUser(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    subscription_tier: str


class AuthSessionData(BaseModel):
    user: AuthUser
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class DeleteAccountData(BaseModel):
    deleted: bool


class MeData(BaseModel):
    user: AuthUser
