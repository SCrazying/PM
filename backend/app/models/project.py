"""项目、成员、TR 模板与节点、任务模型。"""
from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    machine_model: Mapped[str | None] = mapped_column(String(64))
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started", server_default="not_started")
    health: Mapped[str] = mapped_column(String(16), nullable=False, default="on_track", server_default="on_track")
    current_node_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project_node.id", ondelete="SET NULL"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    archived_at = mapped_column(Date, nullable=True)


class ProjectMember(IdMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_member"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    project_role: Mapped[str | None] = mapped_column(String(32))
    is_invested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    joined_at = mapped_column(Date, nullable=True)


class TrTemplate(IdMixin, Base):
    __tablename__ = "tr_template"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    created_at = mapped_column(Date, nullable=True)


class TrTemplateNode(IdMixin, Base):
    __tablename__ = "tr_template_node"

    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tr_template.id", ondelete="CASCADE"), nullable=False)
    node_key: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    review_focus: Mapped[str | None] = mapped_column(Text)


class ProjectNode(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_node"

    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    template_node_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tr_template_node.id", ondelete="SET NULL"))
    node_key: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started", server_default="not_started")
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)


class NodeReview(IdMixin, Base):
    __tablename__ = "node_review"

    project_node_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project_node.id", ondelete="RESTRICT"), nullable=False)
    conclusion: Mapped[str] = mapped_column(String(16), nullable=False)  # pass/conditional_pass/fail
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(Date, nullable=True)


class Task(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "task"

    project_node_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project_node.id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo", server_default="todo")  # todo/in_progress/done
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)
    source_review_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("node_review.id", ondelete="SET NULL"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="RESTRICT"))
