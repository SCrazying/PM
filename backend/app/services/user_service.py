"""用户管理服务（管理员）。"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.responses import BizException, NotFoundError
from app.core.security import hash_password
from app.models.misc import AuditLog
from app.models.user import AuthToken, PasswordReset, User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list[User]:
        return list(self.db.execute(select(User).order_by(User.id)).scalars().all())

    def list_user_options(self) -> list[User]:
        return list(self.db.execute(
            select(User).where(User.status == "active").order_by(User.display_name, User.id)
        ).scalars().all())

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

    def delete_user(self, user_id: int, operator_id: int) -> None:
        """删除用户。存在业务关联数据时拒绝（提示改为停用），防止孤儿数据。"""
        if user_id == operator_id:
            raise BizException("不能删除当前登录账号")
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")
        if user.role == "admin":
            admin_count = self.db.execute(
                select(func.count()).select_from(User).where(User.role == "admin")
            ).scalar()
            if admin_count <= 1:
                raise BizException("系统至少保留一名管理员，无法删除")
        refs = self._find_business_references(user_id)
        if refs:
            raise BizException(f"该用户存在关联数据（{refs}），无法删除；可改为停用该账号")
        # 清理仅认证/审计类的引用后物理删除
        self.db.query(AuthToken).filter(AuthToken.user_id == user_id).delete()
        self.db.query(PasswordReset).filter(
            or_(PasswordReset.user_id == user_id, PasswordReset.reset_by == user_id)
        ).delete(synchronize_session=False)
        self.db.query(AuditLog).filter(AuditLog.actor_id == user_id).update({"actor_id": None})
        self.db.delete(user)
        self.db.commit()

    def _find_business_references(self, user_id: int) -> str:
        """检查会阻塞删除的业务关联表，返回命中的中文标签（逗号分隔）。"""
        from app.models.misc import (
            AiSummary,
            Attachment,
            Notification,
            Progress,
            ProjectWeeklyGoal,
        )
        from app.models.project import (
            NodeReview,
            Project,
            ProjectMember,
            ProjectRoleAssignment,
            Task,
            TrTemplate,
        )

        checks = [
            (Project, (Project.owner_id, Project.created_by), "项目"),
            (ProjectMember, (ProjectMember.user_id,), "项目成员"),
            (ProjectRoleAssignment, (ProjectRoleAssignment.user_id,), "项目角色"),
            (Task, (Task.assignee_id, Task.created_by), "任务"),
            (Progress, (Progress.author_id,), "进展"),
            (NodeReview, (NodeReview.reviewer_id,), "节点评审"),
            (ProjectWeeklyGoal, (ProjectWeeklyGoal.set_by,), "周目标"),
            (Attachment, (Attachment.uploaded_by,), "附件"),
            (AiSummary, (AiSummary.user_id, AiSummary.generated_by), "AI总结"),
            (Notification, (Notification.user_id,), "通知"),
            (TrTemplate, (TrTemplate.created_by,), "模板"),
        ]
        found = []
        for model, columns, label in checks:
            conds = [c == user_id for c in columns if c is not None]
            if self.db.query(model.id).filter(or_(*conds)).first() is not None:
                found.append(label)
        return "、".join(found)
