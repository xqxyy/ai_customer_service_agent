"""创建客服项目核心数据表。

Revision ID: 52203b824be0
Revises:
Create Date: 2026-07-28 17:27:01.154135
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Alembic 版本标识：用来串起迁移链路。
revision: str = "52203b824be0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：创建 Agent 运行、消息、工单和工具日志四张基础表。
def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_run_id"), "agent_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_agent_runs_session_id"), "agent_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_runs_user_id"), "agent_runs", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_session_id"), "messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=100), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_session_id"), "tickets", ["session_id"], unique=False)
    op.create_index(op.f("ix_tickets_ticket_id"), "tickets", ["ticket_id"], unique=True)
    op.create_index(op.f("ix_tickets_user_id"), "tickets", ["user_id"], unique=False)

    op.create_table(
        "tool_call_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=True),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_call_logs_run_id"), "tool_call_logs", ["run_id"], unique=False)
    op.create_index(op.f("ix_tool_call_logs_session_id"), "tool_call_logs", ["session_id"], unique=False)
    op.create_index(op.f("ix_tool_call_logs_tool_name"), "tool_call_logs", ["tool_name"], unique=False)


# 回滚数据库结构：按依赖关系反向删除基础表和索引。
def downgrade() -> None:
    op.drop_index(op.f("ix_tool_call_logs_tool_name"), table_name="tool_call_logs")
    op.drop_index(op.f("ix_tool_call_logs_session_id"), table_name="tool_call_logs")
    op.drop_index(op.f("ix_tool_call_logs_run_id"), table_name="tool_call_logs")
    op.drop_table("tool_call_logs")

    op.drop_index(op.f("ix_tickets_user_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_ticket_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_session_id"), table_name="tickets")
    op.drop_table("tickets")

    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_session_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_agent_runs_user_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_session_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_run_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
