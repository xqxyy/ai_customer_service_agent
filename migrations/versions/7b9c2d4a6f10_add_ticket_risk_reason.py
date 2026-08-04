"""增加工单风险原因和命中关键词字段。

Revision ID: 7b9c2d4a6f10
Revises: 0ba1e4330180
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Alembic 版本标识：该版本把高风险审核原因持久化到 tickets 表。
revision: str = "7b9c2d4a6f10"
down_revision: Union[str, Sequence[str], None] = "0ba1e4330180"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：给工单增加风险原因和命中关键词，便于人工审核时看到触发依据。
def upgrade() -> None:
    op.add_column("tickets", sa.Column("risk_reason", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("matched_keyword", sa.String(length=100), nullable=True))


# 回滚数据库结构：删除本阶段新增的风险解释字段。
def downgrade() -> None:
    op.drop_column("tickets", "matched_keyword")
    op.drop_column("tickets", "risk_reason")
