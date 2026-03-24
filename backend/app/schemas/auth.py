from __future__ import annotations

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    name: str
    role: str
