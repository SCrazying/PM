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

    # 对象存储（项目资料）：backend=local 用本地磁盘（UPLOAD_DIR）；minio 用 MinIO
    # 后期切换正式文件系统时，仅改 .env 即可，代码无需变更
    STORAGE_BACKEND: str = "local"          # local / minio
    MINIO_ENDPOINT: str = ""                 # 如 127.0.0.1:9000
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "pm-system"
    MINIO_SECURE: bool = False

    # 备份
    BACKUP_DIR: str = "./data/backups"

    # CORS（内网前端源，逗号分隔；同源部署可留空）
    CORS_ORIGINS: str = ""


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # 生产红线：JWT_SECRET 必须显式配置，禁止回落到公共默认值（否则任意拿包者可伪造 admin token）
    if s.APP_ENV == "prod" and (not s.JWT_SECRET or s.JWT_SECRET == "change-me-in-prod"):
        raise RuntimeError("生产环境禁止使用默认 JWT_SECRET，请在 .env 配置随机密钥后重启")
    return s


settings = get_settings()
