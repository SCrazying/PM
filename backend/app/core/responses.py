"""统一 API 响应结构 { code, message, data } 与业务异常。"""
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

CODE_OK = 0
CODE_BAD_REQUEST = 400
CODE_UNAUTHORIZED = 401
CODE_FORBIDDEN = 403
CODE_NOT_FOUND = 404
CODE_CONFLICT = 409
CODE_SERVER_ERROR = 500


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": CODE_OK, "message": message, "data": data}


def error(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def page_result(items: list, total: int, page: int, size: int) -> dict:
    return ok({"list": items, "total": total, "page": page, "size": size})


class BizException(Exception):
    """业务异常：抛出后由全局处理器转为统一响应。"""

    def __init__(self, message: str, code: int = CODE_BAD_REQUEST, http_status: int = 200, data: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.data = data


class NotFoundError(BizException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=CODE_NOT_FOUND, http_status=404)


class ForbiddenError(BizException):
    def __init__(self, message: str = "无权限"):
        super().__init__(message, code=CODE_FORBIDDEN, http_status=403)


class UnauthorizedError(BizException):
    def __init__(self, message: str = "未认证或凭证已失效"):
        super().__init__(message, code=CODE_UNAUTHORIZED, http_status=401)


def register_exception_handlers(app) -> None:
    import logging

    logger = logging.getLogger("pm.api")

    @app.exception_handler(BizException)
    async def _biz_handler(request: Request, exc: BizException):
        return JSONResponse(status_code=exc.http_status, content=error(exc.code, exc.message, exc.data))

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        # 兜底，避免泄露内部细节；记录完整 traceback 便于排查
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=error(CODE_SERVER_ERROR, "服务器内部错误"))
