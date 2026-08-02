"""用户管理服务（管理员）。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import BizException, NotFoundError
from app.core.security import hash_password
from app.models.user import AuthToken, PasswordReset, User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list[User]:
        return list(self.db.execute(select(User).order_by(User.id)).scalars().all())

    def create(self, body: UserCreate) -> User:
        exists = self.db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
        if exists:
            raise BizException("用户名已存在", code=409, http_status=409)
        user = User(
            username=body.username,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            role=body.role,
            email=body.email,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user_id: int, body: UserUpdate) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")
        for f in ("display_name", "email", "role"):
            v = getattr(body, f, None)
            if v is not None:
                setattr(user, f, v)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_status(self, user_id: int, status: str) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")
        user.status = status
        if status == "disabled":
            self.db.query(AuthToken).filter(AuthToken.user_id == user_id).update({"revoked": True})
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_password(self, user_id: int, new_password: str, operator_id: int) -> None:
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")
        user.password_hash = hash_password(new_password)
        self.db.add(PasswordReset(user_id=user_id, reset_by=operator_id, new_password_hash=user.password_hash))
        # 吊销其所有 refresh token
        self.db.query(AuthToken).filter(AuthToken.user_id == user_id).update({"revoked": True})
        self.db.commit()
