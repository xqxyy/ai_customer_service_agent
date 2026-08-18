"""
客户信息查询工具

这个文件把“查询客户资料”封装成 LangChain Tool，供 Agent 在用户询问会员等级、
联系方式、客户资料等问题时调用。当前使用模拟数据，后续可以替换成真实 CRM 或用户中心接口
"""

from langchain_core.tools import tool

from backend.app.tools.schemas import ToolTimer, tool_error, tool_success, validate_required_text


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
    timer = ToolTimer()
    user_id, error_code = validate_required_text(user_id, "user_id")

    if error_code:
        return tool_error(
            error_code=error_code,
            status="validation_error",
            message="user_id 不能为空，无法查询客户资料。",
            timer=timer,
            found=False,
        )

    customer = CUSTOMERS.get(user_id)

    if not customer:
        return tool_success(
            status="not_found",
            message="没有找到该用户信息",
            data={"user_id": user_id},
            timer=timer,
            found=False,
        )

    return tool_success(
        status="found",
        message="已找到客户资料",
        data={"customer": customer},
        timer=timer,
        found=True,
        customer=customer,
    )
