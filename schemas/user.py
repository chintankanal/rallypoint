from datetime import datetime
from pydantic import BaseModel
from schemas.enums import UserRole


class UserCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None
    role: UserRole
    academy_id: str | None = None


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    academy_id: str | None
    is_active: bool
    created_at: datetime
