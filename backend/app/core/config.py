"""应用配置：从环境变量读取，支持 .env 文件（本地开发）。"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    APP_NAME: str = "PM-System"
    APP_ENV: str = "dev"               # dev / prod
    API_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "postgresql+psycopg2://pm:pm123@127.0.0.1:5432/pm_system"

    # JWT
    JWT_SECRET: str = "change-me-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = 120
    JWT_REFRESH_TTL_DAY: int = 7

    # 安全
    LOGIN_MAX_FAIL: int = 5
    LOCK_MINUTES: int = 15

    # AI（OpenAI 兼容 API，内网可达）
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SECONDS: int = 60
    AI_MAX_RETRIES: int = 2

    # 附件
    UPLOAD_DIR: str = "./data/uploads"
    ATTACHMENT_MAX_MB: int = 50

    # 备份
    BACKUP_DIR: str = "./data/backups"

    # CORS（内网前端源，逗号分隔；同源部署可留空）
    CORS_ORIGINS: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
