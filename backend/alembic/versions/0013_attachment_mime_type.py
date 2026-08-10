"""attachment.mime_type 加长到 VARCHAR(255)。

背景：xlsx 的 MIME 类型 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
长达 65 字符，超过原 VARCHAR(64) 导致上传报 StringDataRightTruncation(64)。
幂等：列已是 >64 长度则跳过。

Revision ID: 0013_attachment_mime_type
Revises: 0012_project_risk
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_attachment_mime_type"
down_revision = "0012_project_risk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("attachment"):
        return
    # 反射当前列长度，仅当不足 255 时加长
    for col in sa.inspect(bind).get_columns("attachment"):
        if col["name"] == "mime_type":
            cur_len = getattr(col["type"], "length", None)
            if cur_len is None or cur_len < 255:
                op.alter_column("attachment", "mime_type", type_=sa.String(length=255))
            return


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("attachment"):
        return
    op.alter_column("attachment", "mime_type", type_=sa.String(length=64))
