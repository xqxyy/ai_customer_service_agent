"""
SQLAlchemy ORM 表模型文件

这个文件定义项目需要持久化的核心业务表：消息、回答引用来源、工单、工具调用日志和 Agent 执行记录
它存在的原因是：Agent 工程化项目必须能追踪“用户问了什么、Agent 做了什么、调用了什么工具、
用了哪些知识来源、最后为什么进入某个状态”，而不是只把最终回答打印出来


ORM-->Object Relational Mapping 对象关系映射
把数据库里的表，映射成 Python 里的类；
把数据库里的一行数据，映射成 Python 里的一个对象。
Python 类 Message  <->  数据库表 messages
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


# 消息表：保存用户消息和 AI 回复，是多轮会话记忆与工作台展示的基础
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# 回答引用来源表：保存某次 AI 回复引用了哪些 RAG 文档，用于 Trace、评估和页面展示
class MessageSource(Base):
    __tablename__ = "message_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(100), index=True)
    doc_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(200))
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# 工单表：保存 AI 无法直接解决或需要人工审核的问题，是客服系统区别于普通聊天机器人的关键
class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    risk_level: Mapped[str] = mapped_column(String(20), default="normal")
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_dataset: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    queue: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# 工具调用日志表：保存每次 Agent 调用了什么工具、参数是什么、结果是什么、是否失败和耗时多少
class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(100), index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Agent 执行记录表：一条 run 代表一次 /chat 请求，是 Trace 查询和评估脚本的主索引
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
