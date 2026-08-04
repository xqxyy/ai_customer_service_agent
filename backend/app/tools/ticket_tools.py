"""
工单创建工具

这个文件把“创建客服工单”封装成 LangChain Tool，供 Agent 在遇到投诉、赔偿、账号异常、隐私、法律等无法由 AI 直接承诺处理的问题时调用
存在的原因是：客服项目不应该只给一句回答，还要能把需要人工介入的问题沉淀成可跟进的业务记录
"""

import json
from datetime import datetime

from langchain_core.tools import tool

from backend.app.db.session import save_ticket


# 内存工单列表：保留给调试观察；真正可靠的数据会同步写入数据库 tickets 表，可删
TICKETS = []


# LangChain 工具函数：创建工单并根据 risk_level 决定初始状态
@tool(parse_docstring=True)
def create_ticket(
    session_id: str,
    user_id: str,
    title: str,
    description: str,
    priority: str = "normal",
    risk_level: str = "normal",
    risk_reason: str = "",
    matched_keyword: str = "",
) -> str:
    """
    为用户创建客服工单，适用于投诉、赔偿、账号异常、人工处理等问题

    Args:
        session_id: 会话 ID
        user_id: 用户 ID
        title: 工单标题
        description: 工单问题描述
        priority: 工单优先级
        risk_level: 风险等级，高风险会进入人工审核
        risk_reason: 进入人工审核的原因
        matched_keyword: 命中的高风险关键词

    Returns:
        JSON 字符串，包含工单创建结果和工单详情
    """
    ticket_id = f"TICKET-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    status = "pending_review" if risk_level == "high" else "open"       #高风险问题 -> 待人工审核

    ticket = {
        "ticket_id": ticket_id,
        "session_id": session_id,
        "user_id": user_id,
        "title": title,
        "description": description,
        "priority": priority,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "matched_keyword": matched_keyword,
        "status": status,
    }

    TICKETS.append(ticket)
    #把工单保存到数据库
    save_ticket(ticket)

    return json.dumps(
        {
            "created": True,
            "ticket": ticket,
        },
        ensure_ascii=False,
    )
