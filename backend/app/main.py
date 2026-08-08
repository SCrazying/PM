"""FastAPI 应用入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.responses import ok, register_exception_handlers

setup_logging()
logger = get_logger("pm.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PM-System backend starting (env=%s)", settings.APP_ENV)
    yield
    logger.info("PM-System backend stopped")


def _mount_frontend(app: FastAPI) -> None:
    """生产/单机模式：后端直接伺服前端 dist（免 Nginx），一个端口 8001 搞定。
    开发模式（vite 5173）不受影响。"""
    dist_dir = os.getenv("PM_DIST_DIR", "")
    if not dist_dir:
        # 默认相对 backend 上一级的 frontend/dist
        dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    if os.path.isdir(dist_dir):
        from fastapi.responses import FileResponse, JSONResponse

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            # API/文档路径未匹配时返回 JSON 404，不回退到前端
            if full_path == "health" or full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
                return JSONResponse({"code": 404, "message": "接口不存在"}, status_code=404)
            # 真实存在的静态资源直接返回（assets/js/css 等）
            if full_path:
                candidate = os.path.normpath(os.path.join(dist_dir, full_path))
                if candidate.startswith(dist_dir) and os.path.isfile(candidate):
                    return FileResponse(candidate)
            # SPA 路由回退到 index.html（支持 F5 刷新 /board /projects 等）
            index = os.path.join(dist_dir, "index.html")
            if os.path.isfile(index):
                return FileResponse(index)
            return JSONResponse({"code": 404, "message": "not found"}, status_code=404)

        logger.info("生产模式：SPA 伺服前端 %s", dist_dir)
    else:
        logger.info("未找到前端 dist（%s），仅提供 API", dist_dir)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs" if settings.APP_ENV != "prod" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "prod" else None,
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    # CORS（同源部署可留空；前后端分离开发时配置前端源）
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health", tags=["meta"])
    def health():
        return ok({"status": "up"})

    app.include_router(api_router, prefix=settings.API_PREFIX)
    # 静态伺服放最后（catch-all 不抢占 API 路由）
    if settings.APP_ENV == "prod" or os.getenv("PM_SERVE_FRONTEND") == "1":
        _mount_frontend(app)
    return app


app = create_app()
