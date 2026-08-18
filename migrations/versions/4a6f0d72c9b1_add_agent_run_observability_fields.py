"""增加 Agent run 可观测性字段。

Revision ID: 4a6f0d72c9b1
Revises: 9c1e5f2d8a4b
Create Date: 2026-08-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Alembic 版本标识：该版本让 agent_runs 表保存模型、耗时、RAG 和失败类型等复盘字段。
revision: str = "4a6f0d72c9b1"
down_revision: Union[str, Sequence[str], None] = "9c1e5f2d8a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：为一次 Agent 执行补齐可观测性指标。
def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    op.add_column("agent_runs", sa.Column("model_name", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("model_provider", sa.String(length=50), nullable=True))
    op.add_column("agent_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("failure_type", sa.String(length=50), nullable=True))
    op.add_column("agent_runs", sa.Column("rag_hit", sa.Boolean(), nullable=True))
    op.add_column("agent_runs", sa.Column("rag_top_score", sa.Float(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("tool_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_runs",
        sa.Column("ticket_created", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_agent_runs_failure_type"), "agent_runs", ["failure_type"], unique=False)

    if dialect != "sqlite":
        op.alter_column("agent_runs", "tool_count", server_default=None)
        op.alter_column("agent_runs", "ticket_created", server_default=None)


# 回滚数据库结构：移除 Agent run 的扩展观测字段。
def downgrade() -> None:
    op.drop_index(op.f("ix_agent_runs_failure_type"), table_name="agent_runs")
    op.drop_column("agent_runs", "ticket_created")
    op.drop_column("agent_runs", "tool_count")
    op.drop_column("agent_runs", "rag_top_score")
    op.drop_column("agent_runs", "rag_hit")
    op.drop_column("agent_runs", "failure_type")
    op.drop_column("agent_runs", "duration_ms")
    op.drop_column("agent_runs", "model_provider")
    op.drop_column("agent_runs", "model_name")
