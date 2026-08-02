"""Repository 基类：统一软删过滤与通用 CRUD。"""
from datetime import datetime, timezone
from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """带软删过滤的通用 Repository。模型需含 is_deleted 字段（软删表）。"""

    model: Type[ModelT]
    soft_delete: bool = True  # 是否软删表

    def __init__(self, db: Session):
        self.db = db

    def _query(self, include_deleted: bool = False):
        q = select(self.model)
        if self.soft_delete and not include_deleted:
            q = q.where(self.model.is_deleted.is_(False))
        return q

    def get(self, id_: int, include_deleted: bool = False) -> Optional[ModelT]:
        q = self._query(include_deleted).where(self.model.id == id_)
        return self.db.execute(q).scalar_one_or_none()

    def list(self, include_deleted: bool = False, **filters) -> list[ModelT]:
        q = self._query(include_deleted)
        for k, v in filters.items():
            if v is not None and hasattr(self.model, k):
                q = q.where(getattr(self.model, k) == v)
        return list(self.db.execute(q).scalars().all())

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def soft_delete(self, obj: ModelT) -> ModelT:
        if self.soft_delete:
            obj.is_deleted = True
            obj.deleted_at = datetime.now(timezone.utc)
            self.db.flush()
        return obj

    def restore(self, obj: ModelT) -> ModelT:
        if self.soft_delete:
            obj.is_deleted = False
            obj.deleted_at = None
            self.db.flush()
        return obj
