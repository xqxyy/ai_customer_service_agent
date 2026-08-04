"""
SQLAlchemy ORM 基类文件

所有数据库表模型都继承 Base，Alembic 会通过 Base.metadata 读取项目有哪些表
它存在的原因是：迁移工具和 ORM 模型需要一个统一的“表结构登记入口”
"""

from sqlalchemy.orm import DeclarativeBase


# 所有 ORM 表模型的父类，Message、Ticket、ToolCallLog 等表都会继承它。
class Base(DeclarativeBase):
    pass
