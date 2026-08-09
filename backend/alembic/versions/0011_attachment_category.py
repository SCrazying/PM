"""项目资料支持：attachment 增加 category 列，CHECK 放宽允许项目级资料。

背景：项目详情支持资料上传（需求矩阵/方案设计/验证报告等），挂在项目级（node/task/review 均空），
原 CHECK「必须关联其一」需放宽为「关联其一或有分类」。幂等：列已存在则跳过。

Revision ID: 0011_attachment_category
Revises: 0010_weekly_goal_assignee
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_attachment_category"
down_revision = "0010_weekly_goal_assignee"
branch_labels = None
depends_on = None

NEW_CHECK = ("project_node_id IS NOT NULL OR task_id IS NOT NULL OR review_id IS NOT NULL "
             "OR category IS NOT NULL")


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("attachment"):
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("attachment")}
    if "category" not in columns:
        op.add_column("attachment", sa.Column("category", sa.String(length=32), nullable=True))
    # 更新 CHECK 约束（部分迁移用 create_all 建的旧约束名一致，直接 drop/add）
    op.execute("ALTER TABLE attachment DROP CONSTRAINT IF EXISTS ck_attachment_owner")
    op.execute(f"ALTER TABLE attachment ADD CONSTRAINT ck_attachment_owner CHECK ({NEW_CHECK})")


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("attachment"):
        return
    columns = {c["name"] for c in sa.inspect(bind).get_columns("attachment")}
    if "category" in columns:
        # 恢复旧 CHECK 前先清掉项目级资料（否则旧约束不满足）
        op.execute("ALTER TABLE attachment DROP CONSTRAINT IF EXISTS ck_attachment_owner")
        op.execute("ALTER TABLE attachment ADD CONSTRAINT ck_attachment_owner CHECK ("
                   "project_node_id IS NOT NULL OR task_id IS NOT NULL OR review_id IS NOT NULL)")
        op.drop_column("attachment", "category")
