"""
知识库检索工具

这个文件把 RAG 检索封装成 LangChain Tool，供 Agent 在回答退款、售后、物流、发票、隐私等政策类问题时调用
存在的原因是：政策答案必须来自知识库依据，不能让大模型凭经验编造；同时这里会把 Milvus 临时不可用转换成结构化降级结果，避免接口直接 500
"""

import json
from datetime import datetime
from time import perf_counter

from langchain_core.tools import tool

from backend.app.rag.retriever import search_documents


# 生成当前时间字符串：工具日志会记录开始和结束时间，便于前端 Trace 展示耗时
def _now_iso() -> str:
    return datetime.now().isoformat()


# LangChain 工具函数：查询知识库并返回结构化 JSON，Agent 根据 found/status 决定是否回答
@tool(parse_docstring=True)
def search_knowledge_base(query: str) -> str:
    """
    查询客服知识库，返回与用户问题相关的政策内容

    Args:
        query: 用户的问题或搜索关键词

    Returns:
        JSON 字符串，包含查询词、命中文档、检索状态和耗时信息
    """
    started_at = _now_iso()
    start_time = perf_counter()

    try:
        results = search_documents(query)
    except Exception as error:
        ended_at = _now_iso()
        return json.dumps(
            {
                "query": query,
                "status": "unavailable",
                "found": False,
                "results": [],
                "message": "知识库暂时不可用，请不要编造答案。",
                "error": "rag_unavailable",
                "error_detail": str(error),
                "error_type": type(error).__name__,
                "unavailable": True,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": int((perf_counter() - start_time) * 1000),
            },
            ensure_ascii=False,
        )

    ended_at = _now_iso()
    return json.dumps(
        {
            "query": query,
            "status": "hit" if results else "no_answer",
            "found": len(results) > 0,
            "results": results,
            "unavailable": False,
            "message": "已命中知识库" if results else "知识库没有找到明确依据。",
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": int((perf_counter() - start_time) * 1000),
        },
        ensure_ascii=False,
    )
