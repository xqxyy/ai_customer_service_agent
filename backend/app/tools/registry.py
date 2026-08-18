"""业务工具规格注册表。

这里不是 LangChain 的执行入口，而是给 API、工作台和面试讲解使用的工具协议说明：
每个工具有哪些入参、返回哪些标准字段、可能出现哪些错误码。
"""

from __future__ import annotations


TOOL_SPECS = [
    {
        "name": "search_knowledge_base",
        "title": "知识库检索",
        "description": "检索客服政策、售后、物流、发票、隐私等 RAG 知识库内容。",
        "inputs": [
            {"name": "query", "type": "string", "required": True, "description": "用户问题或检索关键词"},
        ],
        "outputs": ["ok", "status", "found", "results", "message", "duration_ms", "error_code"],
        "error_codes": ["missing_query", "rag_unavailable"],
    },
    {
        "name": "get_latest_order",
        "title": "订单查询",
        "description": "根据 user_id 查询用户最近一笔订单状态和物流信息。",
        "inputs": [
            {"name": "user_id", "type": "string", "required": True, "description": "用户 ID"},
        ],
        "outputs": ["ok", "status", "found", "order", "message", "duration_ms", "error_code"],
        "error_codes": ["missing_user_id"],
    },
    {
        "name": "get_customer_info",
        "title": "客户资料",
        "description": "根据 user_id 查询客户姓名、会员等级和脱敏联系方式。",
        "inputs": [
            {"name": "user_id", "type": "string", "required": True, "description": "用户 ID"},
        ],
        "outputs": ["ok", "status", "found", "customer", "message", "duration_ms", "error_code"],
        "error_codes": ["missing_user_id"],
    },
    {
        "name": "create_ticket",
        "title": "创建工单",
        "description": "为无法自动处理或高风险问题创建客服工单，高风险默认进入 pending_review。",
        "inputs": [
            {"name": "session_id", "type": "string", "required": True, "description": "会话 ID"},
            {"name": "user_id", "type": "string", "required": True, "description": "用户 ID"},
            {"name": "title", "type": "string", "required": True, "description": "工单标题"},
            {"name": "description", "type": "string", "required": True, "description": "工单描述"},
            {"name": "priority", "type": "string", "required": False, "description": "优先级"},
            {"name": "risk_level", "type": "string", "required": False, "description": "风险等级"},
        ],
        "outputs": ["ok", "status", "created", "ticket", "message", "duration_ms", "error_code"],
        "error_codes": [
            "missing_session_id",
            "missing_user_id",
            "missing_title",
            "missing_description",
            "invalid_priority",
            "invalid_risk_level",
            "ticket_save_failed",
        ],
    },
]


def get_tool_specs() -> list[dict]:
    return TOOL_SPECS
