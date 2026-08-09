"""去掉「归档」状态：存量 archived 迁移为 completed（归档并入已完成）。

背景：归档 与 已完成 重叠，设计上合并——终态统一用「已完成」，彻底移除用删除（回收站）。
仅数据迁移，无结构变更（status 为 varchar，无值级约束）。

Revision ID: 0009_drop_archived
Revises: 0008_machine_model
"""
from alembic import op


revision = "0009_drop_archived"
down_revision = "0008_machine_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 存量 archived 项目并入已完成（软删行一并处理，状态不影响回收站显示）
    op.execute("UPDATE project SET status = 'completed' WHERE status = 'archived'")


def downgrade() -> None:
    # 反向不还原（无法区分原 completed 与 merged 的 archived），保持只进不退
    pass
