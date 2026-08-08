"""机型管理表 machine_model。

Revision ID: 0008_machine_model
Revises: 0007_project_name_unique
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_machine_model"
down_revision = "0007_project_name_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("machine_model"):
        op.create_table(
            "machine_model",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    existing = {i["name"] for i in sa.inspect(bind).get_indexes("machine_model")}
    if "ux_machine_model_name" not in existing:
        op.execute("CREATE UNIQUE INDEX ux_machine_model_name ON machine_model(name) WHERE NOT is_deleted")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_machine_model_name")
    op.drop_table("machine_model")
