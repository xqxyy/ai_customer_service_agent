"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# Alembic 版本标识：生成迁移文件后不要随意改 revision/down_revision。
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


# 升级数据库结构：在这里写新增表、字段、索引等操作。
def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


# 回滚数据库结构：在这里写和 upgrade 相反的删除或恢复操作。
def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
