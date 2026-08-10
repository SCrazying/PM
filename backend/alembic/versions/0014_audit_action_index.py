"""audit_log 补 action 索引（审计查询按 action 过滤）。

Revision ID: 0014_audit_action_index
Revises: 0013_attachment_mime_type
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_audit_action_index"
down_revision = "0013_attachment_mime_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("audit_log"):
        return
    existing = {i["name"] for i in sa.inspect(bind).get_indexes("audit_log")}
    if "ix_audit_action" not in existing:
        op.create_index("ix_audit_action", "audit_log", ["action"])


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("audit_log"):
        op.drop_index("ix_audit_action", table_name="audit_log")
