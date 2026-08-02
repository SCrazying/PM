"""FastAPI 依赖：当前用户解析与权限档校验（admin/owner/member/login/self）。"""
from fastapi import Depends, Header

from app.core.responses import ForbiddenError, UnauthorizedError
from app.core.security import decode_token


def get_current_user(authorization: str = Header(default="")) -> dict:
    """从 Authorization: Bearer 解析当前用户。返回 {'user_id','role'}。M1 接 DB 校验状态。"""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("缺少认证凭证")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise UnauthorizedError()
    if payload.get("type") != "access":
        raise UnauthorizedError("凭证类型不正确")
    return {"user_id": int(payload["sub"]), "role": payload.get("role", "member")}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise ForbiddenError("仅管理员可操作")
    return user


def require_login(user: dict = Depends(get_current_user)) -> dict:
    return user


def require_self_or_admin(user_id: int, user: dict = Depends(get_current_user)) -> dict:
    """personal 域：仅本人或 admin。"""
    if user["role"] != "admin" and user["user_id"] != user_id:
        raise ForbiddenError("仅本人或管理员可操作")
    return user
