"""项目名称唯一：project.name 部分唯一索引（未软删）。

Revision ID: 0007_project_name_unique
Revises: 0006_weekly_goal_item
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_project_name_unique"
down_revision = "0006_weekly_goal_item"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {i["name"] for i in sa.inspect(bind).get_indexes("project")}
    if "ux_project_name" not in existing:
        op.execute(
            "CREATE UNIQUE INDEX ux_project_name ON project(name) WHERE NOT is_deleted"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_project_name")
