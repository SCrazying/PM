"""认证路由。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import ok
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserBrief,
)
from app.services.audit_service import record_audit
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    svc = AuthService(db)
    user, access, refresh = svc.login(body.username, body.password)
    record_audit(db, user.id, "login", "user", str(user.id), None, request.client.host if request.client else None)
    return ok(LoginResponse(access_token=access, refresh_token=refresh, user=UserBrief.model_validate(user)).model_dump())


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    user, access = svc.refresh(body.refresh_token)
    return ok(TokenResponse(access_token=access).model_dump())


@router.post("/logout")
def logout(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    AuthService(db).logout(user["user_id"])
    record_audit(db, user["user_id"], "logout", "user", str(user["user_id"]))
    return ok(message="已登出")


@router.get("/me")
def me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.user import User
    u = db.get(User, user["user_id"])
    return ok(UserBrief.model_validate(u).model_dump())


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.user import User
    u = db.get(User, user["user_id"])
    AuthService(db).change_password(u, body.old_password, body.new_password)
    record_audit(db, user["user_id"], "update", "user", str(user["user_id"]), {"action": "change_password"})
    return ok(message="密码已修改，请重新登录")
