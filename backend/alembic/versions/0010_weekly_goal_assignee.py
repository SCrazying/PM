"""周目标条目增加负责人：weekly_goal_item.user_id（绑定参与项目的成员）。

背景：添加周目标时可选择项目成员作为负责人，方便目标与任务/人绑定。
user_id 可空，存量条目不受影响；幂等（表/列已存在时跳过）。

Revision ID: 0010_weekly_goal_assignee
Revises: 0009_drop_archived
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_weekly_goal_assignee"
down_revision = "0009_drop_archived"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("weekly_goal_item"):
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("weekly_goal_item")}
    if "user_id" not in columns:
        op.add_column("weekly_goal_item", sa.Column("user_id", sa.BigInteger(), nullable=True))
        # 用显式 SQL 命名约束，避免 alembic create_foreign_key 在带 target_metadata 时改写为自动名
        op.execute(
            'ALTER TABLE weekly_goal_item ADD CONSTRAINT fk_weekly_goal_item_user '
            'FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE RESTRICT'
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("weekly_goal_item"):
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("weekly_goal_item")}
    if "user_id" in columns:
        # 兼容显式命名（0010）与 alembic 自动命名（0001 create_all 建表）两种约束名
        op.execute("ALTER TABLE weekly_goal_item DROP CONSTRAINT IF EXISTS fk_weekly_goal_item_user")
        op.execute("ALTER TABLE weekly_goal_item DROP CONSTRAINT IF EXISTS weekly_goal_item_user_id_fkey")
        op.drop_column("weekly_goal_item", "user_id")
