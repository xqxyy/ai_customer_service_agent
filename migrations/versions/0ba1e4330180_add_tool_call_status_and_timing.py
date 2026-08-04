"""增加工具调用状态、错误和耗时字段。

Revision ID: 0ba1e4330180
Revises: 2d717491a894
Create Date: 2026-07-28 23:41:00.155829
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Alembic 版本标识：该版本让工具调用日志具备可观测性字段。
revision: str = "0ba1e4330180"
down_revision: Union[str, Sequence[str], None] = "2d717491a894"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：给工具日志增加状态、错误、开始结束时间和耗时。
def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    op.add_column(
        "tool_call_logs",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="success"),
    )
    if dialect != "sqlite":
        op.alter_column("tool_call_logs", "status", server_default=None)

    op.add_column("tool_call_logs", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("tool_call_logs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("tool_call_logs", sa.Column("ended_at", sa.DateTime(), nullable=True))
    op.add_column("tool_call_logs", sa.Column("duration_ms", sa.Integer(), nullable=True))

    if dialect != "sqlite":
        op.alter_column(
            "tool_call_logs",
            "result",
            existing_type=postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        )


# 回滚数据库结构：移除工具调用可观测性字段，并恢复 result 非空约束。
def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect != "sqlite":
        op.alter_column(
            "tool_call_logs",
            "result",
            existing_type=postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
        )

    op.drop_column("tool_call_logs", "duration_ms")
    op.drop_column("tool_call_logs", "ended_at")
    op.drop_column("tool_call_logs", "started_at")
    op.drop_column("tool_call_logs", "error")
    op.drop_column("tool_call_logs", "status")
