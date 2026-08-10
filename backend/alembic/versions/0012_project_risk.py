"""项目独立风险表 project_risk（项目详情「风险管理」单独添加）。

与进展内填报的 progress.risk 并存：风险管理区合并展示，独立风险可增删/关闭。

Revision ID: 0012_project_risk
Revises: 0011_attachment_category
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_project_risk"
down_revision = "0011_attachment_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("project_risk"):
        op.create_table(
            "project_risk",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("risk", sa.String(length=500), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
    existing = {i["name"] for i in sa.inspect(bind).get_indexes("project_risk")}
    if "ix_project_risk_project" not in existing:
        op.create_index("ix_project_risk_project", "project_risk", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("project_risk"):
        op.drop_index("ix_project_risk_project", table_name="project_risk")
        op.drop_table("project_risk")
