"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-02

说明：
  * 普通表结构由 SQLAlchemy metadata 创建（create_all 等价）
  * 软删兼容的部分唯一索引、进展表达式唯一索引需手写（autogenerate 不会生成）
  * 与 db/schema.sql 保持一致
"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# 需要 WHERE NOT is_deleted 的部分唯一索引（表, 索引名, 列）
PARTIAL_UNIQUE_INDEXES = [
    ("project", "ux_project_code", "code"),
    ("project_member", "ux_member", "project_id, user_id"),
    ("project_weekly_goal", "ux_weekly_goal", "project_id, week_start"),
]

# 软删表的部分普通索引（表, 索引名, 列）
PARTIAL_INDEXES = [
    ("project", "ix_project_status", "status"),
    ("project", "ix_project_owner", "owner_id"),
    ("project", "ix_project_machine", "machine_model"),
    ("project_member", "ix_member_user", "user_id"),
    ("task", "ix_task_node", "project_node_id, status"),
    ("task", "ix_task_assignee", "assignee_id, status"),
    ("task", "ix_task_project", "project_id, status"),
    ("progress", "ix_progress_proj_date", "project_id, progress_date"),
    ("progress", "ix_progress_author_date", "author_id, progress_date"),
    ("attachment", "ix_attachment_project", "project_id"),
    ("attachment", "ix_attachment_node", "project_node_id"),
    ("attachment", "ix_attachment_task", "task_id"),
    ("attachment", "ix_attachment_review", "review_id"),
]

# 无条件唯一索引（表, 索引名, 列）
PLAIN_UNIQUE_INDEXES = [
    ("user", "ux_user_username", "username"),
    ("tr_template", "ux_tr_template_name", "name"),
    ("tr_template_node", "ux_ttn_key", "template_id, node_key"),
    ("tr_template_node", "ux_ttn_seq", "template_id, sequence"),
    ("progress_task_link", "ux_ptl", "progress_id, task_id"),
    ("ai_summary", "ux_ai_summary", "user_id, period_type, period_start"),
    ("notification", "ux_notification_dedup", "dedup_key"),
    ("project_node", "ux_node_seq", "project_id, sequence"),  # 注意：schema 中带软删，见下
]

# 普通索引（表, 索引名, 列）
PLAIN_INDEXES = [
    ("auth_token", "ix_auth_token_user", "user_id"),
    ("password_reset", "ix_password_reset_user", "user_id"),
    ("node_review", "ix_node_review_node", "project_node_id"),
    ("progress_task_link", "ix_ptl_task", "task_id"),
    ("notification", "ix_notification_user", "user_id, is_read"),
    ("audit_log", "ix_audit_target", "target_type, target_id"),
    ("audit_log", "ix_audit_actor", "actor_id, created_at"),
    ("audit_log", "ix_audit_time", "created_at"),
]


def upgrade() -> None:
    # 1) 建表（含列、普通约束、CHECK）
    from app.models import Base
    from alembic import context

    bind = context.get_bind()
    Base.metadata.create_all(bind=bind)

    def ui(idx_sql: str) -> None:
        op.execute(idx_sql)

    # 2) 部分唯一索引（软删兼容）
    for table, name, cols in PARTIAL_UNIQUE_INDEXES:
        ui(f'CREATE UNIQUE INDEX {name} ON "{table}" ({cols}) WHERE NOT is_deleted')
    # project_node.sequence 也带软删
    ui('CREATE UNIQUE INDEX ux_node_seq ON "project_node" (project_id, sequence) WHERE NOT is_deleted')

    # 3) 进展表达式唯一索引（COALESCE 处理 node NULL）
    ui(
        'CREATE UNIQUE INDEX uq_progress ON "progress" '
        '(author_id, project_id, COALESCE(project_node_id, 0), progress_date) WHERE NOT is_deleted'
    )

    # 4) 软删表的部分普通索引
    for table, name, cols in PARTIAL_INDEXES:
        ui(f'CREATE INDEX {name} ON "{table}" ({cols}) WHERE NOT is_deleted')

    # 5) 无条件唯一索引（去掉已单独处理的 ux_node_seq）
    for table, name, cols in PLAIN_UNIQUE_INDEXES:
        if name == "ux_node_seq":
            continue
        ui(f'CREATE UNIQUE INDEX {name} ON "{table}" ({cols})')

    # 6) 普通索引
    for table, name, cols in PLAIN_INDEXES:
        ui(f'CREATE INDEX {name} ON "{table}" ({cols})')


def downgrade() -> None:
    from app.models import Base
    from alembic import context

    bind = context.get_bind()
    Base.metadata.drop_all(bind=bind)
