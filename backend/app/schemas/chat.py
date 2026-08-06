"""
聊天接口数据模型

这个文件用 Pydantic 定义 /chat 接口的请求和响应结构
存在的原因是：FastAPI 可以基于这些模型自动做参数校验、生成 Swagger 文档，并保证前端拿到稳定字段
"""

from pydantic import BaseModel, Field


# RAG 引用来源模型：表示一次回答引用了哪篇知识库文档
class Source(BaseModel):
    doc_id: str
    title: str
    source: str
    source_path: str = ""
    # 以下字段来自 RAG 元数据，前端和 Trace 可据此判断来源类型、业务领域和适用地区。
    doc_type: str = ""
    business_area: str = ""
    risk_level: str = ""
    source_kind: str = ""
    jurisdiction: str = ""
    score: float


# 聊天请求模型：用户调用 /chat 时必须传入会话、用户和消息内容
class ChatRequest(BaseModel):
    session_id: str = Field(default="demo_session")
    user_id: str = Field(default="user-001")
    message: str = Field(min_length=1)


# 聊天响应模型：后端返回 run_id、回答、业务状态和引用来源
class ChatResponse(BaseModel):
    run_id: str
    session_id: str
    answer: str
    status: str = "answered"
    sources: list[Source] = Field(default_factory=list)
