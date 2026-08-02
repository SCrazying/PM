"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    return app


app = create_app()
