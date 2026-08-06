"""
数据库业务访问层

这个文件负责把 ORM 模型封装成项目业务函数，例如保存消息、创建工单、保存工具日志、
按 run_id 查询 Trace、给前端工作台返回列表数据。它存在的原因是：Agent 和 API 路由
不应该直接写数据库细节，而应该调用这里的函数，让数据库访问边界更清楚
"""

import json
from datetime import datetime

from sqlalchemy import inspect, select, text

from backend.app.db.models_sqlalchemy import (
    AgentRun,
    Message,
    MessageSource,
    Ticket,
    ToolCallLog,
)
from backend.app.db.session_sqlalchemy import SessionLocal, engine


# 健康检查要求存在的核心表；缺任何一张都说明数据库迁移没有到位
REQUIRED_TABLES = {
    "agent_runs",
    "message_sources",
    "messages",
    "tickets",
    "tool_call_logs",
}


# 把字符串时间转成 datetime，便于写入 DateTime 字段
def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


# 把 datetime 转成 JSON 友好的 ISO 字符串，便于接口返回
def _format_datetime(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


# 初始化数据库入口；当前项目建表由 Alembic 管理，这里只做健康检查
def init_db():
    return check_database_health()


# 检查数据库是否可连接、核心表是否存在，用于 /health 依赖状态展示
def check_database_health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        missing_tables = sorted(REQUIRED_TABLES - existing_tables)

        return {
            "ok": not missing_tables,
            "dialect": engine.dialect.name,
            "missing_tables": missing_tables,
        }
    except Exception as error:
        return {
            "ok": False,
            "dialect": engine.dialect.name,
            "missing_tables": sorted(REQUIRED_TABLES),
            "error": str(error),
            "error_type": type(error).__name__,
        }


# 保存一条聊天消息，返回 message.id，方便 assistant 回复再绑定引用来源
def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    run_id: str | None = None,
) -> int:
    with SessionLocal() as db:
        message = Message(      #创建一个 ORM 对象
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
        )
        db.add(message)     #把这个对象加入数据库会话
        db.commit()         #提交事务，把数据写进数据库
        db.refresh(message) #从数据库重新刷新这个对象：有些字段是数据库生成的，db.commit()后数据库才真正生成这些值，refresh会把数据库里的最新值重新加载到 Python 对象里
        return message.id   # refresh后才能拿到真实的数据库 ID


# 保存 AI 回复引用的 RAG 来源，支撑“回答依据来自哪里”的可观测能力。
def save_message_sources(message_id: int, run_id: str, sources: list[dict]):
    with SessionLocal() as db:
        for source in sources:
            db.add(
                MessageSource(
                    message_id=message_id,
                    run_id=run_id,
                    doc_id=source.get("doc_id", ""),
                    title=source.get("title", ""),
                    source=source.get("source", ""),
                    source_path=source.get("source_path", ""),
                    score=float(source.get("score", 0) or 0),
                )
            )

        db.commit()


# 按 run_id 查询一次 Agent 执行主记录，给 /agent-runs/{run_id} 使用
def get_agent_run(run_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            select(AgentRun).where(AgentRun.run_id == run_id)
        ).scalar_one_or_none()

    if row is None:
        return None

    return {
        "id": row.id,
        "run_id": row.run_id,
        "session_id": row.session_id,
        "user_id": row.user_id,
        "input": row.input,
        "output": row.output,
        "status": row.status,
        "error": row.error,
        "started_at": _format_datetime(row.started_at),
        "ended_at": _format_datetime(row.ended_at),
    }


# 按 run_id 查询本次请求保存的用户消息和 AI 回复
def list_messages_by_run_id(run_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Message)
            .where(Message.run_id == run_id)
            .order_by(Message.id.asc())
        ).scalars().all()

    return [
        {
            "id": row.id,
            "run_id": row.run_id,
            "session_id": row.session_id,
            "user_id": row.user_id,
            "role": row.role,
            "content": row.content,
            "created_at": _format_datetime(row.created_at),
        }
        for row in rows
    ]


# 按 run_id 查询本次请求的工具调用链路
def list_tool_calls_by_run_id(run_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(ToolCallLog)
            .where(ToolCallLog.run_id == run_id)
            .order_by(ToolCallLog.id.asc())
        ).scalars().all()

    return [
        {
            "id": row.id,
            "run_id": row.run_id,
            "session_id": row.session_id,
            "tool_name": row.tool_name,
            "arguments": row.arguments or {},
            "result": row.result or {},
            "created_at": _format_datetime(row.created_at),
            "status": row.status,
            "error": row.error,
            "started_at": _format_datetime(row.started_at),
            "ended_at": _format_datetime(row.ended_at),
            "duration_ms": row.duration_ms,
        }
        for row in rows
    ]


# 按 run_id 查询本次回复引用了哪些知识库文档
def list_message_sources_by_run_id(run_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(MessageSource)
            .where(MessageSource.run_id == run_id)
            .order_by(MessageSource.id.asc())
        ).scalars().all()

    return [
        {
            "id": row.id,
            "message_id": row.message_id,
            "run_id": row.run_id,
            "doc_id": row.doc_id,
            "title": row.title,
            "source": row.source,
            "source_path": row.source_path,
            "score": row.score,
            "created_at": _format_datetime(row.created_at),
        }
        for row in rows
    ]


# 保存客服工单，普通问题进入 open，高风险问题通常进入 pending_review
def save_ticket(ticket: dict):
    with SessionLocal() as db:
        db.add(             #创建一个 Ticket ORM 对象，并加入数据库会话
            Ticket(
                ticket_id=ticket["ticket_id"],
                session_id=ticket["session_id"],
                user_id=ticket["user_id"],
                title=ticket["title"],
                description=ticket["description"],
                priority=ticket.get("priority", "normal"),
                risk_level=ticket.get("risk_level", "normal"),
                risk_reason=ticket.get("risk_reason", ""),
                matched_keyword=ticket.get("matched_keyword", ""),
                source_dataset=ticket.get("source_dataset"),
                external_id=ticket.get("external_id"),
                category=ticket.get("category"),
                queue=ticket.get("queue"),
                language=ticket.get("language"),
                tags=ticket.get("tags"),
                status=ticket["status"],
            )
        )
        db.commit()


# 保存 Agent 工具调用日志，包括参数、结果、错误、状态和耗时
def save_tool_call(
    run_id: str,
    session_id: str,
    tool_name: str,
    arguments: dict,
    result: dict | None,
    status: str = "success",
    error: str | None = None,
    started_at=None,
    ended_at=None,
    duration_ms: int | None = None,
):
    with SessionLocal() as db:
        db.add(
            ToolCallLog(
                run_id=run_id,
                session_id=session_id,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                status=status,
                error=error,
                started_at=_to_datetime(started_at) if started_at else None,
                ended_at=_to_datetime(ended_at) if ended_at else None,
                duration_ms=duration_ms,
            )
        )
        db.commit()


# 保存一次 Agent 执行主记录，用 run_id 串起消息、工具调用、引用来源和最终状态
def save_agent_run(
    run_id,
    session_id,
    user_id,
    input_text,
    output_text,
    status,
    error,
    started_at,
    ended_at,
):
    with SessionLocal() as db:
        db.add(
            AgentRun(
                run_id=run_id,
                session_id=session_id,
                user_id=user_id,
                input=input_text,
                output=output_text,
                status=status,
                error=error,
                started_at=_to_datetime(started_at),
                ended_at=_to_datetime(ended_at),
            )
        )
        db.commit()


# 查询最近消息列表，供工作台聊天窗口展示
def list_messages(limit: int = 40) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Message).order_by(Message.id.desc()).limit(limit)
        ).scalars().all()

    return [
        {
            "id": row.id,
            "session_id": row.session_id,
            "user_id": row.user_id,
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]


# 查询最近工单列表，供工作台工单面板展示
def list_tickets(limit: int = 30) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Ticket)
            .order_by(Ticket.id.desc())
            .limit(limit)
        ).scalars().all()

    return [
        {
            "id": row.id,
            "ticket_id": row.ticket_id,
            "session_id": row.session_id,
            "user_id": row.user_id,
            "title": row.title,
            "description": row.description,
            "priority": row.priority,
            "risk_level": row.risk_level,
            "risk_reason": row.risk_reason,
            "matched_keyword": row.matched_keyword,
            "source_dataset": row.source_dataset,
            "external_id": row.external_id,
            "category": row.category,
            "queue": row.queue,
            "language": row.language,
            "tags": row.tags or [],
            "status": row.status,
            "created_at": _format_datetime(row.created_at),
        }
        for row in rows
    ]


# 查询最近工具调用日志，供工作台 Trace 面板展示
def list_tool_calls(limit: int = 30) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(ToolCallLog)
            .order_by(ToolCallLog.id.desc())
            .limit(limit)
        ).scalars().all()

    return [
        {
            "id": row.id,
            "run_id": row.run_id,
            "session_id": row.session_id,
            "tool_name": row.tool_name,
            "arguments": row.arguments or {},
            "result": row.result or {},
            "created_at": _format_datetime(row.created_at),
            "status": row.status,
            "error": row.error,
            "started_at": _format_datetime(row.started_at),
            "ended_at": _format_datetime(row.ended_at),
            "duration_ms": row.duration_ms,
        }
        for row in rows
    ]


# 修改工单状态，返回 True/False 让 API 层决定返回 200 还是 404
def update_ticket_status(ticket_id: str, status: str) -> bool:
    with SessionLocal() as db:
        ticket = db.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        ).scalar_one_or_none()

        if ticket is None:
            return False

        ticket.status = status
        db.commit()
        return True


# 尝试把 JSON 字符串转成对象，保留给兼容旧数据或调试时使用
def _parse_json(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


# 查询某个 session 最近几轮消息，让 Agent 能获得基础多轮上下文
def list_recent_messages(session_id: str, limit: int = 8) -> list[dict]:
    with SessionLocal() as db:  #连接数据库创建会话，得到一个 db 操作对象，代码块结束后自动关闭这个会话
        rows = db.execute(      #执行一条 SQLAlchemy 查询
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.id.desc())
            .limit(limit)
        ).scalars().all()       #返回Message 模型对象的所有结果，变成列表

    return [
        {
            "role": row.role,
            "content": row.content,
            "created_at": _format_datetime(row.created_at),
        }
        for row in reversed(rows)
    ]
