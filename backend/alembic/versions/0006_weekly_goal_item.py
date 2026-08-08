"""周目标条目化：weekly_goal_item 表。

Revision ID: 0006_weekly_goal_item
Revises: 0005_template_subnode
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_weekly_goal_item"
down_revision = "0005_template_subnode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("weekly_goal_item"):
        op.create_table(
            "weekly_goal_item",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("goal", sa.String(length=255), nullable=False),
            sa.Column("deadline", sa.Date(), nullable=True),
            sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("done_at", sa.Date(), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
    existing_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("weekly_goal_item")}
    if "ix_weekly_goal_item_project" not in existing_indexes:
        op.create_index("ix_weekly_goal_item_project", "weekly_goal_item", ["project_id", "week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_goal_item_project", table_name="weekly_goal_item")
    op.drop_table("weekly_goal_item")
