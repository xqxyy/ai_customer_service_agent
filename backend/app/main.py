"""
FastAPI 应用入口文件

这个文件负责把客服 Agent、RAG、工单、数据库和前端工作台统一暴露成 HTTP 服务
它存在的原因是：项目不能只停留在命令行脚本，而要能通过 API、Swagger 和浏览器页面
展示完整业务链路
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app.agents.customer_service_agent import CustomerServiceAgent
from backend.app.db.session import (
    check_database_health,
    get_agent_run,
    init_db,
    list_message_sources_by_run_id,
    list_messages,
    list_messages_by_run_id,
    list_tickets,
    list_tool_calls,
    list_tool_calls_by_run_id,
    update_ticket_status,
)
from backend.app.rag.documents import load_processed_documents
from backend.app.rag.retriever import check_milvus_health
from backend.app.schemas.chat import ChatRequest, ChatResponse


# 静态资源目录：工作台页面和前端脚本都放在 backend/app/static 下
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# FastAPI 应用对象：Swagger/OpenAPI 文档会根据路由和 Pydantic 模型自动生成
app = FastAPI(title="智能客服运营平台 Agent")

# 静态文件挂载：让浏览器可以加载 index.html、app.js 和 styles.css
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 全局 Agent 实例：避免每个请求都重新初始化模型、系统提示词和工具列表
agent = CustomerServiceAgent()

# 工单状态更新请求模型：限制 PATCH 接口只接收 status 字段
class TicketStatusUpdate(BaseModel):
    status: str

# 应用启动钩子：启动时检查数据库状态；真实建表和改表由 Alembic 负责
@app.on_event("startup")
def startup():
    init_db()

# 健康检查接口：同时检查数据库和 Milvus，帮助定位依赖服务是否可用
@app.get("/health")
def health():
    database = check_database_health()
    milvus = check_milvus_health()

    return {
        "status": "ok" if database["ok"] and milvus["ok"] else "degraded",
        "database": database,
        "milvus": milvus,
    }


# 首页接口：返回浏览器可打开的客服工作台页面。
@app.get("/", include_in_schema=False)
def workbench():
    return FileResponse(STATIC_DIR / "index.html")


# 工作台数据接口：一次性返回聊天、工单、工具日志和知识库文档列表。
@app.get("/workbench/state")
def workbench_state():
    return {
        "messages": list_messages(),
        "tickets": list_tickets(),
        "tool_calls": list_tool_calls(),
        # 每次请求读取最新 documents.jsonl，避免重建 RAG 后工作台仍显示旧知识库清单。
        "documents": load_processed_documents(),
    }


# 工单状态更新接口：让前端可以把工单改为 open、pending_review、resolved 或 closed。
@app.patch("/tickets/{ticket_id}/status")
def change_ticket_status(ticket_id: str, payload: TicketStatusUpdate):
    allowed_statuses = {"open", "pending_review", "resolved", "closed"}

    if payload.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Unsupported ticket status")

    updated = update_ticket_status(ticket_id, payload.status)

    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "updated": True,
        "ticket_id": ticket_id,
        "status": payload.status,
    }


# 聊天接口：接收用户问题，交给 Agent 完成决策、工具调用、落库和回复。
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    return agent.run(request)


# Agent 执行详情接口：按 run_id 查询消息、工具调用和引用来源，支撑 Trace 展示。
@app.get("/agent-runs/{run_id}")
def get_agent_run_detail(run_id: str):
    run = get_agent_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")

    return {
        "run": run,
        "messages": list_messages_by_run_id(run_id),
        "tool_calls": list_tool_calls_by_run_id(run_id),
        "sources": list_message_sources_by_run_id(run_id),
    }
