"""
知识库检索工具

这个文件把 RAG 检索封装成 LangChain Tool，供 Agent 在回答退款、售后、物流、发票、隐私等政策类问题时调用
存在的原因是：政策答案必须来自知识库依据，不能让大模型凭经验编造；同时这里会把 Milvus 临时不可用转换成结构化降级结果，避免接口直接 500
"""

from langchain_core.tools import tool

from backend.app.rag.retriever import search_documents
from backend.app.tools.schemas import ToolTimer, tool_error, tool_success, validate_required_text


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
    timer = ToolTimer()
    query, error_code = validate_required_text(query, "query")

    if error_code:
        return tool_error(
            error_code=error_code,
            status="validation_error",
            message="检索问题不能为空。",
            timer=timer,
            query=query,
            found=False,
            results=[],
            unavailable=False,
        )

    try:
        results = search_documents(query)
    except Exception as error:
        return tool_error(
            error_code="rag_unavailable",
            status="unavailable",
            message="知识库暂时不可用，请不要编造答案。",
            error_detail=str(error),
            error_type=type(error).__name__,
            timer=timer,
            query=query,
            found=False,
            results=[],
            unavailable=True,
        )

    return tool_success(
        status="hit" if results else "no_answer",
        message="已命中知识库" if results else "知识库没有找到明确依据。",
        data={"results": results},
        timer=timer,
        query=query,
        found=len(results) > 0,
        results=results,
        unavailable=False,
    )
