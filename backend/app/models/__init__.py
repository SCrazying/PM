"""ORM 模型包：导入全部模型以便 Alembic autogenerate 发现。"""
from app.models.base import Base
from app.models.misc import (
    AiSummary,
    Attachment,
    AuditLog,
    Config,
    Notification,
    Progress,
    ProgressTaskLink,
    ProjectWeeklyGoal,
)
from app.models.project import (
    NodeReview,
    Project,
    ProjectMember,
    ProjectNode,
    ProjectRoleAssignment,
    Task,
    TrTemplate,
    TrTemplateNode,
)
from app.models.user import AuthToken, PasswordReset, User

__all__ = [
    "Base",
    "User", "AuthToken", "PasswordReset",
    "Project", "ProjectMember", "ProjectRoleAssignment", "TrTemplate", "TrTemplateNode", "ProjectNode", "NodeReview", "Task",
    "Progress", "ProgressTaskLink", "ProjectWeeklyGoal", "Attachment",
    "AiSummary", "AuditLog", "Config", "Notification",
]
