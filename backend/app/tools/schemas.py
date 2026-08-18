"""工具调用的统一返回结构和轻量校验。

LangChain Tool 最终仍然返回 JSON 字符串，但内部统一包含 ok/status/error_code/message/data
等字段，便于 Agent Trace、评估脚本和前端工作台用同一种方式判断工具是否成功。
"""

from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter
from typing import Any


# 简单计时器：让每个工具都能返回 started_at、ended_at 和 duration_ms。
class ToolTimer:
    def __init__(self):
        self.started_at = datetime.now().isoformat()
        self._start = perf_counter()

    def timing(self) -> dict:
        return {
            "started_at": self.started_at,
            "ended_at": datetime.now().isoformat(),
            "duration_ms": int((perf_counter() - self._start) * 1000),
        }


# 返回 JSON 字符串，保留中文，避免工作台出现转义后的内容。
def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


# 标准成功返回：extra 用于保留工具自己的业务字段，兼容旧前端和旧评估逻辑。
def tool_success(
    *,
    status: str = "success",
    message: str = "",
    data: dict | None = None,
    timer: ToolTimer | None = None,
    **extra: Any,
) -> str:
    payload = {
        "ok": True,
        "status": status,
        "error_code": "",
        "error": "",
        "message": message,
        "data": data or {},
        **extra,
    }
    if timer:
        payload.update(timer.timing())
    return dumps(payload)


# 标准错误返回：工具失败也转成结构化 JSON，让 Agent 可以走兜底话术。
def tool_error(
    *,
    error_code: str,
    message: str,
    status: str = "tool_error",
    error_detail: str = "",
    error_type: str = "",
    timer: ToolTimer | None = None,
    **extra: Any,
) -> str:
    payload = {
        "ok": False,
        "status": status,
        "error_code": error_code,
        "error": error_code,
        "message": message,
        "error_detail": error_detail,
        "error_type": error_type,
        "data": {},
        **extra,
    }
    if timer:
        payload.update(timer.timing())
    return dumps(payload)


# 必填字符串校验：返回清洗后的值和错误码，工具自己决定如何转成业务提示。
def validate_required_text(value: str, field_name: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", f"missing_{field_name}"
    return text, ""
