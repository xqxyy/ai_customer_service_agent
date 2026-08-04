"""增加 Agent Trace 的消息来源表。

Revision ID: 2d717491a894
Revises: 52203b824be0
Create Date: 2026-07-28 23:17:13.413959
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Alembic 版本标识：该版本基于核心数据表之后继续扩展。
revision: str = "2d717491a894"
down_revision: Union[str, Sequence[str], None] = "52203b824be0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：增加 message_sources 表，并给 messages 增加 run_id 以关联一次 Agent 执行。
def upgrade() -> None:
    op.create_table(
        "message_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("doc_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_sources_doc_id"), "message_sources", ["doc_id"], unique=False)
    op.create_index(op.f("ix_message_sources_message_id"), "message_sources", ["message_id"], unique=False)
    op.create_index(op.f("ix_message_sources_run_id"), "message_sources", ["run_id"], unique=False)
    op.add_column("messages", sa.Column("run_id", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_messages_run_id"), "messages", ["run_id"], unique=False)


# 回滚数据库结构：删除 run_id 索引和消息来源表。
def downgrade() -> None:
    op.drop_index(op.f("ix_messages_run_id"), table_name="messages")
    op.drop_column("messages", "run_id")
    op.drop_index(op.f("ix_message_sources_run_id"), table_name="message_sources")
    op.drop_index(op.f("ix_message_sources_message_id"), table_name="message_sources")
    op.drop_index(op.f("ix_message_sources_doc_id"), table_name="message_sources")
    op.drop_table("message_sources")
