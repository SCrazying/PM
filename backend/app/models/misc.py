"""进展、关联、周目标、附件、AI 总结、审计、配置、通知模型。"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin

# PG 用 JSONB，其它方言（如 SQLite 测试库）退化为通用 JSON
JsonbType = JSONB().with_variant(JSON(), "sqlite")


class Progress(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "progress"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    project_node_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project_node.id", ondelete="RESTRICT"))
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    progress_date: Mapped[date] = mapped_column(Date, nullable=False)
    today_work: Mapped[str] = mapped_column(Text, nullable=False)
    tomorrow_plan: Mapped[str | None] = mapped_column(Text)
    risk: Mapped[str | None] = mapped_column(Text)
    risk_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class ProgressTaskLink(IdMixin, Base):
    __tablename__ = "progress_task_link"

    progress_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("progress.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("task.id", ondelete="CASCADE"), nullable=False)


class ProjectWeeklyGoal(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_weekly_goal"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    set_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))


class WeeklyGoalItem(IdMixin, TimestampMixin, Base):
    """项目周目标条目：goal + 截止时间 + 完成状态（周会视图逐条点击完成）。"""
    __tablename__ = "weekly_goal_item"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    goal: Mapped[str] = mapped_column(String(255), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    done_at: Mapped[date | None] = mapped_column(Date)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Attachment(IdMixin, SoftDeleteMixin, Base):
    __tablename__ = "attachment"
    __table_args__ = (
        CheckConstraint(
            "project_node_id IS NOT NULL OR task_id IS NOT NULL OR review_id IS NOT NULL",
            name="ck_attachment_owner",
        ),
    )

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    project_node_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project_node.id", ondelete="RESTRICT"))
    task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("task.id", ondelete="RESTRICT"))
    review_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("node_review.id", ondelete="RESTRICT"))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(64))
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiSummary(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_summary"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    period_type: Mapped[str] = mapped_column(String(8), nullable=False)  # month/quarter/year
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    edited_content: Mapped[str | None] = mapped_column(Text)
    source_snapshot: Mapped[dict | None] = mapped_column(JsonbType)
    model: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="generating", server_default="generating")
    error: Mapped[str | None] = mapped_column(String(255))
    generated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"

    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JsonbType)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(IdMixin, Base):
    __tablename__ = "notification"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    dedup_key: Mapped[str | None] = mapped_column(String(128))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
