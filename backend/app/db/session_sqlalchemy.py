"""
SQLAlchemy 数据库连接文件

这个文件负责根据 DATABASE_URL 创建数据库 engine 和 SessionLocal
它存在的原因是：业务代码不应该自己到处创建数据库连接，而应该通过统一 Session 工厂访问数据库
这样从 SQLite 切换到 PostgreSQL 时，业务函数基本不用改
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import get_settings


settings = get_settings()

# 根据数据库类型设置不同连接参数：SQLite 需要允许跨线程，PostgreSQL 需要短连接超时
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif settings.database_url.startswith("postgresql"):
    connect_args = {"connect_timeout": settings.database_connect_timeout_seconds}

# engine 负责维护底层数据库连接池，并执行 SQLAlchemy 生成的 SQL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

# SessionLocal 是数据库会话工厂，每次业务操作都会创建一个短生命周期 Session
SessionLocal = sessionmaker(
    autocommit=False,   #不会自动提交事务
    autoflush=False,    #SQLAlchemy 不会在某些查询前自动把内存里的改动 flush 到数据库
    bind=engine,        # Session 绑定到哪个数据库引擎，engine 里保存了数据库连接信息
)


# FastAPI 依赖注入函数：后续如果路由函数需要直接拿 db，可以通过 Depends(get_db) 使用
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
