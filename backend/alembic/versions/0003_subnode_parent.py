"""节点子节点支持：project_node 加 parent_id，调整顺序唯一索引。

Revision ID: 0003_subnode_parent
Revises: 0002_project_role_assignment
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_subnode_parent"
down_revision = "0002_project_role_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("project_node")]
    if "parent_id" not in cols:
        op.add_column(
            "project_node",
            sa.Column("parent_id", sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            "fk_project_node_parent", "project_node", "project_node",
            ["parent_id"], ["id"], ondelete="CASCADE",
        )
    # 顺序唯一索引改为按父子域区分（子节点在各父下独立编号）
    idx = sa.inspect(bind).get_indexes("project_node")
    if any(i["name"] == "ux_node_seq" for i in idx):
        op.drop_index("ux_node_seq", table_name="project_node")
    op.execute(
        "CREATE UNIQUE INDEX ux_node_seq ON project_node "
        "(project_id, COALESCE(parent_id, 0), sequence) WHERE NOT is_deleted"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_node_seq")
    op.execute("CREATE UNIQUE INDEX ux_node_seq ON project_node (project_id, sequence) WHERE NOT is_deleted")
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("project_node")]
    if "parent_id" in cols:
        op.drop_constraint("fk_project_node_parent", "project_node", type_="foreignkey")
        op.drop_column("project_node", "parent_id")
