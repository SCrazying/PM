"""对象存储后端：本地磁盘 / MinIO 可切换（后期接正式文件系统时仅改 .env）。

统一接口：put / get / delete / exists。返回的 file_path 含义：
  * local：磁盘绝对路径（供 FileResponse 直接返回）
  * minio：bucket 内对象名（get 下载到临时文件供 FileResponse）
"""
from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("pm.storage")


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, content: bytes) -> str: ...

    @abstractmethod
    def get_path(self, key: str) -> str:
        """返回可供 FileResponse 使用的本地路径（minio 下载到临时文件）。"""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorage(StorageBackend):
    def _abs(self, key: str) -> str:
        return os.path.join(settings.UPLOAD_DIR, key)

    def put(self, key: str, content: bytes) -> str:
        path = self._abs(key)
        os.makedirs(os.path.dirname(path) or settings.UPLOAD_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def get_path(self, key: str) -> str:
        return self._abs(key)

    def delete(self, key: str) -> None:
        try:
            os.remove(self._abs(key))
        except OSError:
            pass

    def exists(self, key: str) -> bool:
        return os.path.exists(self._abs(key))


class MinioStorage(StorageBackend):
    def __init__(self) -> None:
        from minio import Minio  # 延迟导入：未启用 minio 时无需依赖
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put(self, key: str, content: bytes) -> str:
        import io
        self._client.put_object(self._bucket, key, io.BytesIO(content), length=len(content))
        return key  # 对象名即存储路径

    def get_path(self, key: str) -> str:
        tmp = os.path.join(tempfile.gettempdir(), f"pm_minio_{os.path.basename(key)}")
        self._client.fget_object(self._bucket, key, tmp)
        return tmp

    def delete(self, key: str) -> None:
        try:
            self._client.remove_object(self._bucket, key)
        except Exception as e:  # noqa: BLE001
            logger.warning("minio 删除失败 %s: %s", key, e)

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception:  # noqa: BLE001
            return False


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """按配置返回存储后端（缓存单例）。STORAGE_BACKEND=minio 时用 MinIO，否则本地磁盘。"""
    global _backend
    if _backend is None:
        if settings.STORAGE_BACKEND.lower() == "minio" and settings.MINIO_ENDPOINT:
            try:
                _backend = MinioStorage()
                logger.info("存储后端：MinIO %s/%s", settings.MINIO_ENDPOINT, settings.MINIO_BUCKET)
            except Exception as e:  # noqa: BLE001
                logger.warning("MinIO 初始化失败（%s），回退本地磁盘", e)
                _backend = LocalStorage()
        else:
            _backend = LocalStorage()
            logger.info("存储后端：本地磁盘 %s", settings.UPLOAD_DIR)
    return _backend


def reset_storage() -> None:
    """测试/配置变更后重置单例。"""
    global _backend
    _backend = None
