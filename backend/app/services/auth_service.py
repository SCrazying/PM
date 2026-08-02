"""认证服务：登录（含锁定）、登出、改密、刷新。"""
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import AuthToken, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def _get_by_username(self, username: str) -> User | None:
        return self.db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    def login(self, username: str, password: str) -> tuple[User, str, str]:
        user = self._get_by_username(username)
        if not user or user.status != "active":
            raise UnauthorizedError("用户名或密码错误")

        # 锁定检查
        if user.locked_until and user.locked_until > _now():
            raise UnauthorizedError("账号已锁定，请稍后再试")

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= settings.LOGIN_MAX_FAIL:
                user.locked_until = _now() + timedelta(minutes=settings.LOCK_MINUTES)
                user.failed_login_count = 0
            self.db.commit()
            raise UnauthorizedError("用户名或密码错误")

        # 成功：重置计数、签发 token、持久化 refresh
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = _now()

        access = create_access_token(user.id, user.role)
        refresh = create_refresh_token(user.id)
        self.db.add(
            AuthToken(
                user_id=user.id,
                refresh_token_hash=hash_token(refresh),
                expires_at=_now() + timedelta(days=settings.JWT_REFRESH_TTL_DAY),
                revoked=False,
            )
        )
        self.db.commit()
        return user, access, refresh

    def refresh(self, refresh_token: str) -> tuple[User, str]:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            raise UnauthorizedError("refresh token 无效或已过期")
        if payload.get("type") != "refresh":
            raise UnauthorizedError("凭证类型不正确")
        user_id = int(payload["sub"])

        # 校验 refresh 未被吊销（在 auth_token 表中且未 revoked、未过期）
        tokens = self.db.execute(
            select(AuthToken).where(AuthToken.user_id == user_id, AuthToken.revoked.is_(False))
        ).scalars().all()
        if not any(t.refresh_token_hash == hash_token(refresh_token) and t.expires_at > _now() for t in tokens):
            raise UnauthorizedError("refresh token 已失效")

        user = self.db.get(User, user_id)
        if not user or user.status != "active":
            raise UnauthorizedError("账号不可用")
        return user, create_access_token(user.id, user.role)

    def logout(self, user_id: int) -> None:
        # 吊销该用户全部 refresh token（单点退出）
        self.db.query(AuthToken).filter(AuthToken.user_id == user_id).update({"revoked": True})
        self.db.commit()

    def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise UnauthorizedError("原密码错误")
        user.password_hash = hash_password(new_password)
        # 改密后吊销其它 refresh token（强制重登）
        self.db.query(AuthToken).filter(AuthToken.user_id == user.id).update({"revoked": True})
        self.db.commit()
