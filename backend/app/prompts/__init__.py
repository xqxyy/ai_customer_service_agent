"""Prompt 模板模块。

这个包把 Agent 的系统提示词和可复用 Prompt 片段从业务流程代码中拆出来。
这样做的原因是：面试或维护时可以单独展示 Prompt 工程设计，而不是在 Agent 主流程里找一大段字符串。
"""

from backend.app.prompts.customer_service import (
    CUSTOMER_SERVICE_AGENT_SYSTEM_PROMPT,
    get_prompt_templates,
)

__all__ = [
    "CUSTOMER_SERVICE_AGENT_SYSTEM_PROMPT",
    "get_prompt_templates",
]
