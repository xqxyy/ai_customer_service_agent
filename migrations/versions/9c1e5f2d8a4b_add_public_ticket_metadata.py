"""给工单增加公开数据集导入元数据字段。

Revision ID: 9c1e5f2d8a4b
Revises: 7b9c2d4a6f10
Create Date: 2026-08-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# Alembic 版本标识：该版本让 tickets 表能记录公开数据集来源和分类信息。
revision: str = "9c1e5f2d8a4b"
down_revision: Union[str, Sequence[str], None] = "7b9c2d4a6f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 升级数据库结构：增加外部数据来源、分类、队列、语言和标签，方便批量导入公开工单。
def upgrade() -> None:
    op.add_column("tickets", sa.Column("source_dataset", sa.String(length=100), nullable=True))
    op.add_column("tickets", sa.Column("external_id", sa.String(length=200), nullable=True))
    op.add_column("tickets", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("tickets", sa.Column("queue", sa.String(length=100), nullable=True))
    op.add_column("tickets", sa.Column("language", sa.String(length=30), nullable=True))
    op.add_column("tickets", sa.Column("tags", sa.JSON(), nullable=True))

    op.create_index("ix_tickets_source_dataset", "tickets", ["source_dataset"])
    op.create_index("ix_tickets_external_id", "tickets", ["external_id"])
    op.create_index("ix_tickets_category", "tickets", ["category"])


# 回滚数据库结构：删除公开数据集导入相关字段和索引。
def downgrade() -> None:
    op.drop_index("ix_tickets_category", table_name="tickets")
    op.drop_index("ix_tickets_external_id", table_name="tickets")
    op.drop_index("ix_tickets_source_dataset", table_name="tickets")

    op.drop_column("tickets", "tags")
    op.drop_column("tickets", "language")
    op.drop_column("tickets", "queue")
    op.drop_column("tickets", "category")
    op.drop_column("tickets", "external_id")
    op.drop_column("tickets", "source_dataset")
