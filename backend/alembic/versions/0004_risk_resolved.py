"""进展风险可关闭：progress 加 risk_resolved。

Revision ID: 0004_risk_resolved
Revises: 0003_subnode_parent
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_risk_resolved"
down_revision = "0003_subnode_parent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("progress")]
    if "risk_resolved" not in cols:
        op.add_column(
            "progress",
            sa.Column("risk_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("progress")]
    if "risk_resolved" in cols:
        op.drop_column("progress", "risk_resolved")
