"""
订单查询工具

这个文件把“查询用户最近订单状态和物流信息”封装成 LangChain Tool
存在的原因是：订单状态属于业务系统数据，不应该让大模型凭空回答，而应该通过工具查询后再回复。当前使用模拟订单，后续可以替换成真实订单系统接口。
"""

from langchain_core.tools import tool

from backend.app.tools.schemas import ToolTimer, tool_error, tool_success, validate_required_text


# 模拟订单数据：用于展示 Agent 如何调用业务工具查询订单
ORDERS = {
    "user-001": [
        {
            "order_id": "ORDER-1001",
            "product": "智能耳机",
            "status": "已发货",
            "logistics": "顺丰速运，预计明天送达",
        }
    ]
}


# LangChain 工具函数：根据 user_id 查询用户最近一笔订单
@tool(parse_docstring=True)
def get_latest_order(user_id: str) -> str:
    """
    查询用户最新订单状态和物流信息。

    Args:
        user_id: 用户 ID。

    Returns:
        JSON 字符串，包含是否找到订单以及订单详情。
    """
    timer = ToolTimer()
    user_id, error_code = validate_required_text(user_id, "user_id")

    if error_code:
        return tool_error(
            error_code=error_code,
            status="validation_error",
            message="user_id 不能为空，无法查询订单。",
            timer=timer,
            found=False,
        )

    orders = ORDERS.get(user_id, [])

    if not orders:
        return tool_success(
            status="not_found",
            message="没有找到订单",
            data={"user_id": user_id},
            timer=timer,
            found=False,
        )

    return tool_success(
        status="found",
        message="已找到最近订单",
        data={"order": orders[0]},
        timer=timer,
        found=True,
        order=orders[0],
    )
