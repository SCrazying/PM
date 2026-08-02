"""项目固定角色分配。

Revision ID: 0002_project_role_assignment
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_project_role_assignment"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("project_role_assignment"):
        op.create_table(
            "project_role_assignment",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint(
                "role IN ('SE', 'TPM', 'TL/FO', 'CodeReview')",
                name="ck_project_role_assignment_role",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "role", "user_id", name="ux_project_role_assignment"),
        )
    existing_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("project_role_assignment")}
    if "ix_project_role_assignment_project" not in existing_indexes:
        op.create_index("ix_project_role_assignment_project", "project_role_assignment", ["project_id"])
    if "ix_project_role_assignment_user" not in existing_indexes:
        op.create_index("ix_project_role_assignment_user", "project_role_assignment", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_project_role_assignment_user", table_name="project_role_assignment")
    op.drop_index("ix_project_role_assignment_project", table_name="project_role_assignment")
    op.drop_table("project_role_assignment")
