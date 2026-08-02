"""用户管理路由；用户选择项对已登录用户开放，管理操作仍需管理员。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.responses import ok
from app.schemas.user import ResetPasswordRequest, StatusUpdate, UserCreate, UserOut, UserUpdate
from app.services.audit_service import record_audit
from app.services.user_service import UserService

router = APIRouter()


@router.get("/options")
def list_user_options(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([{"id": u.id, "display_name": u.display_name, "role": u.role} for u in UserService(db).list_user_options()])


@router.get("")
def list_users(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    users = UserService(db).list_users()
    return ok([UserOut.model_validate(u).model_dump() for u in users])


@router.post("")
def create_user(body: UserCreate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    u = UserService(db).create(body)
    record_audit(db, user["user_id"], "create", "user", str(u.id), {"username": u.username})
    return ok(UserOut.model_validate(u).model_dump(), message="创建成功")


@router.put("/{user_id}")
def update_user(user_id: int, body: UserUpdate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    u = UserService(db).update(user_id, body)
    record_audit(db, user["user_id"], "update", "user", str(user_id), body.model_dump(exclude_none=True))
    return ok(UserOut.model_validate(u).model_dump(), message="更新成功")


@router.patch("/{user_id}/status")
def set_status(user_id: int, body: StatusUpdate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    u = UserService(db).set_status(user_id, body.status)
    record_audit(db, user["user_id"], "update", "user", str(user_id), {"status": body.status})
    return ok(UserOut.model_validate(u).model_dump(), message="状态已更新")


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetPasswordRequest, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    UserService(db).reset_password(user_id, body.new_password, user["user_id"])
    record_audit(db, user["user_id"], "reset_password", "user", str(user_id))
    return ok(message="密码已重置")
