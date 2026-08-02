"""ORM 公共基类与软删混入。"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# PG 用 BIGINT，SQLite（测试库）用 INTEGER 以保证自增主键
BigIdType = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdMixin:
    id: Mapped[int] = mapped_column(BigIdType, primary_key=True, autoincrement=True)


__all__ = ["Base", "TimestampMixin", "SoftDeleteMixin", "IdMixin", "BigIdType"]
