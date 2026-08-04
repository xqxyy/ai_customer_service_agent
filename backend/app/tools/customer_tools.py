"""
客户信息查询工具

这个文件把“查询客户资料”封装成 LangChain Tool，供 Agent 在用户询问会员等级、
联系方式、客户资料等问题时调用。当前使用模拟数据，后续可以替换成真实 CRM 或用户中心接口
"""

import json

from langchain_core.tools import tool


# 模拟客户数据：当前阶段先用固定数据展示工具调用链路
CUSTOMERS = {
    "user-001": {
        "user_id": "user-001",
        "name": "张三",
        "level": "VIP",
        "phone": "138****8888",
    }
}


# LangChain 工具函数：根据 user_id 查询客户信息，并返回 JSON 字符串
@tool(parse_docstring=True)
def get_customer_info(user_id: str) -> str:
    """
    查询客户资料。

    Args:
        user_id: 用户 ID。

    Returns:
        JSON 字符串，包含是否找到客户以及客户详情。
    """
    customer = CUSTOMERS.get(user_id)

    if not customer:
        return json.dumps(
            {
                "found": False,
                "message": "没有找到该用户信息",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "found": True,
            "customer": customer,
        },
        ensure_ascii=False,
    )
