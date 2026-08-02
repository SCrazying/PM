"""用户相关 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6)
    role: str = "member"           # admin / member
    email: Optional[str] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    email: Optional[str]
    role: str
    status: str
    last_login_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)


class StatusUpdate(BaseModel):
    status: str  # active / disabled
