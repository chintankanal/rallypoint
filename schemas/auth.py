from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str | None = None
    otp_code: str | None = None


class OTPRequest(BaseModel):
    email: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "PLAYER"   # only PLAYER / COACH / REFEREE / UMPIRE allowed
    gender: str | None = None
    academy_id: str | None = None
    phone: str | None = None


class TokenResponse(BaseModel):
    token: str
    user_id: str
    role: str
    name: str | None = None
    academy_id: str | None
    academy_name: str | None = None
    player_id: str | None = None
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
