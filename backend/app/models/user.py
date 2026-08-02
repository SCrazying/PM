"""用户与认证相关模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "user"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member", server_default="member")  # admin/member
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")  # active/disabled
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthToken(IdMixin, Base):
    __tablename__ = "auth_token"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordReset(IdMixin, Base):
    __tablename__ = "password_reset"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    reset_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    new_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
