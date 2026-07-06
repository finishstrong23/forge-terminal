"""
Pydantic models for auth endpoints.

Shared between:
- routes/auth.py — POST /api/v1/auth/register, POST /api/v1/auth/login,
  GET /api/v1/auth/me
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # Max 72: bcrypt truncates beyond 72 bytes (see core/security.py).
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    subscription_tier: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
