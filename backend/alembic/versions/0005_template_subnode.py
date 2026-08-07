"""TR 模板默认子节点：tr_template_subnode 表。

Revision ID: 0005_template_subnode
Revises: 0004_risk_resolved
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_template_subnode"
down_revision = "0004_risk_resolved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("tr_template_subnode"):
        op.create_table(
            "tr_template_subnode",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("template_node_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["template_node_id"], ["tr_template_node.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("template_node_id", "sequence", name="ux_template_subnode_seq"),
        )
    existing_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("tr_template_subnode")}
    if "ix_template_subnode_node" not in existing_indexes:
        op.create_index("ix_template_subnode_node", "tr_template_subnode", ["template_node_id"])


def downgrade() -> None:
    op.drop_index("ix_template_subnode_node", table_name="tr_template_subnode")
    op.drop_table("tr_template_subnode")
