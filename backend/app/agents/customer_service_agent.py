"""
客服 Agent 主流程文件。

这个文件负责把 LangChain Agent、业务工具、RAG、风险兜底、数据库持久化串成一次
完整的客服处理流程。它存在的原因是：真实客服 Agent 不是只调用大模型生成一句话，
而是要判断问题类型、调用工具、保存过程、处理高风险问题、返回可追踪的 run_id，
并把每一步落到数据库里方便前端和评估查看。
"""

import json
from datetime import datetime
from uuid import uuid4

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from backend.app.core.config import get_settings
from backend.app.db.session import (
    list_recent_messages,
    save_agent_run,
    save_message,
    save_message_sources,
    save_tool_call,
)
from backend.app.prompts import CUSTOMER_SERVICE_AGENT_SYSTEM_PROMPT
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.risk_service import detect_risk
from backend.app.tools.customer_tools import get_customer_info
from backend.app.tools.knowledge_tools import search_knowledge_base
from backend.app.tools.order_tools import get_latest_order
from backend.app.tools.ticket_tools import create_ticket


# 全局配置：读取模型、API 地址、数据库、RAG 等运行参数
settings = get_settings()


# Agent 可调用工具列表：LangChain 会根据工具名、参数说明和 docstring 决定何时调用
tools = [
    search_knowledge_base,
    get_latest_order,
    create_ticket,
    get_customer_info,
]


# 客服 Agent 类：封装一次 /chat 请求从输入到回复的完整执行流程
class CustomerServiceAgent:
    # 初始化模型和 LangChain Agent；应用启动时创建一次，避免每个请求重复初始化
    def __init__(self):
        self.model_name = "deepseek-v4-flash"
        self.model_provider = "deepseek"

        model = init_chat_model(
            model=self.model_name,
            model_provider=self.model_provider,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=60,
            max_retries=2,
        )

        self.agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=CUSTOMER_SERVICE_AGENT_SYSTEM_PROMPT,
        )

    # 执行一次客服对话：保存消息、前置风险检查、调用 Agent、保存 Trace 并返回响应
    def run(self, request: ChatRequest) -> ChatResponse:
        run_id = str(uuid4())       #串联messages、tool_call_logs、message_sources、agent_runs  可查一次 Agent 执行的完整过程
        started_at = datetime.now().isoformat()

        #异常保护       出错后 except 会记录失败的 Agent run
        #可能的错误：模型调用失败、Milvus 检索失败、数据库写入失败、工具执行失败
        try:
            messages = self._build_messages(request)

            save_message(
                run_id=run_id,
                session_id=request.session_id,
                user_id=request.user_id,
                role="user",
                content=request.message,
            )

            # 高风险问题前置拦截：投诉/赔偿等问题直接创建人工审核工单，避免先进入自由回答   创建一个空的 Trace 容器
            precheck_trace = {
                "tool_calls": [],
                "sources": [],
            }
            #检查当前用户问题是不是高风险     是就会创建人工审核工单
            fallback = self._create_high_risk_ticket_if_needed(request, precheck_trace)

            if fallback:
                #把刚刚自动创建工单的工具调用记录放进 Trace
                precheck_trace["tool_calls"].append(fallback["tool_call"])
                #把工具调用日志保存到数据库 tool_call_logs 表
                self._save_tool_call_logs(run_id, request.session_id, precheck_trace)

                answer = fallback["answer"]
                status = self._infer_status(precheck_trace)

                assistant_message_id = save_message(
                    run_id=run_id,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=answer,
                )

                save_message_sources(
                    message_id=assistant_message_id,
                    run_id=run_id,
                    sources=[],
                )

                ended_at = datetime.now().isoformat()

                #保存一次完整 Agent 执行记录到 agent_runs 表
                self._save_agent_run_record(
                    run_id=run_id,
                    request=request,
                    answer=answer,
                    status=status,
                    error=None,
                    started_at=started_at,
                    ended_at=ended_at,
                    trace=precheck_trace,
                )

                return ChatResponse(
                    run_id=run_id,
                    session_id=request.session_id,
                    answer=answer,
                    status=status,
                    sources=[],
                )

            # 普通问题进入 LangChain Agent，让模型决定是否调用知识库、订单、客户或工单工具
            result = self.agent.invoke({"messages": messages})

            messages = result["messages"]
            answer = messages[-1].content
            trace = self._build_trace(messages)

            # Agent 调用后再次兜底：如果模型漏掉高风险工单，后端仍然强制创建
            fallback = self._create_high_risk_ticket_if_needed(request, trace)

            if fallback:
                trace["tool_calls"].append(fallback["tool_call"])
                answer = fallback["answer"]

            self._save_tool_call_logs(run_id, request.session_id, trace)
            status = self._infer_status(trace)

            assistant_message_id = save_message(
                run_id=run_id,
                session_id=request.session_id,
                user_id=request.user_id,
                role="assistant",
                content=answer,
            )

            save_message_sources(
                message_id=assistant_message_id,
                run_id=run_id,
                sources=trace.get("sources", []),
            )

            ended_at = datetime.now().isoformat()

            self._save_agent_run_record(
                run_id=run_id,
                request=request,
                answer=answer,
                status=status,
                error=None,
                started_at=started_at,
                ended_at=ended_at,
                trace=trace,
            )

            return ChatResponse(
                run_id=run_id,
                session_id=request.session_id,
                answer=answer,
                status=status,
                sources=trace.get("sources", []),
            )

        except Exception as error:
            ended_at = datetime.now().isoformat()

            self._save_agent_run_record(
                run_id=run_id,
                request=request,
                answer=None,
                status="failed",
                error=str(error),
                started_at=started_at,
                ended_at=ended_at,
                trace={"tool_calls": [], "sources": []},
                failure_type="model_error",
            )
            raise

    # 组装历史消息和当前问题：给模型提供最近几轮上下文，并带上 session_id/user_id。
    def _build_messages(self, request: ChatRequest) -> list[dict]:
        history = list_recent_messages(request.session_id, limit=8)

        messages = [
            {
                "role": row["role"],
                "content": row["content"],
            }
            for row in history
        ]

        messages.append(
            {
                "role": "user",
                "content": (
                    f"session_id: {request.session_id}\n"
                    f"user_id: {request.user_id}\n"
                    f"message: {request.message}\n"
                ),
            }
        )

        return messages

    # 从messages中提取工具调用过程：包括工具名、参数和工具返回结果。
    def _build_trace(self, messages: list) -> dict:
        tool_calls_by_id = {}       #工具调用 ID
        ordered_tool_calls = []     #按顺序保存工具调用

        for message in messages:
            for tool_call in getattr(message, "tool_calls", []) or []:  #getattr：有 tool_calls，就取出来，没有久[]
                #每一次工具调用过程会生成一个唯一id call_xxx
                tool_call_id = tool_call.get("id")
                call_info = {                       #构造一个标准工具调用记录
                    "id": tool_call_id,
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args", {}),
                    "result": {},
                }
                ordered_tool_calls.append(call_info)

                if tool_call_id:
                    tool_calls_by_id[tool_call_id] = call_info

            tool_call_id = getattr(message, "tool_call_id", None)   #再检查当前 message 是不是工具返回消息
            if tool_call_id and tool_call_id in tool_calls_by_id:
                tool_calls_by_id[tool_call_id]["result"] = self._parse_tool_result(    #把工具返回内容解析后，填回对应的工具调用记录
                    getattr(message, "content", "")
                )

        #从工具调用结果里提取 RAG 来源
        sources = self._extract_sources(ordered_tool_calls)

        return {
            "tool_calls": ordered_tool_calls,
            "sources": sources,
        }

    # 解析工具返回值：工具通常返回 JSON 字符串，这里统一转成 dict 方便后续判断状态
    def _parse_tool_result(self, content) -> dict:
        if isinstance(content, dict):
            return content

        if not isinstance(content, str):
            return {"raw": content}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "status": "parse_error",
                "error_code": "model_parse_error",
                "error": "model_parse_error",
                "message": "工具返回不是合法 JSON。",
                "raw": content,
            }

        if isinstance(parsed, dict):
            return parsed

        return {
            "ok": False,
            "status": "parse_error",
            "error_code": "model_parse_error",
            "error": "model_parse_error",
            "message": "工具返回不是 JSON 对象。",
            "raw": parsed,
        }

    # 从知识库工具结果里提取引用来源：最终进入 ChatResponse.sources 和 message_sources 表
    def _extract_sources(self, tool_calls: list[dict]) -> list[dict]:
        sources = []
        seen = set()    #创建一个集合，用来去重

        # tool_calls列表，这一次 Agent 执行过程中，所有工具调用记录的集合
        for tool_call in tool_calls:
            if tool_call.get("name") != "search_knowledge_base":
                continue

            result = tool_call.get("result", {})

            for doc in result.get("results", []):
                doc_id = doc.get("doc_id")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                sources.append(
                    {
                        "doc_id": doc_id,
                        "title": doc.get("title", ""),
                        "source": doc.get("source", ""),
                        "source_path": doc.get("source_path", ""),
                        "doc_type": doc.get("doc_type", ""),
                        "business_area": doc.get("business_area", ""),
                        "risk_level": doc.get("risk_level", ""),
                        "source_kind": doc.get("source_kind", ""),
                        "jurisdiction": doc.get("jurisdiction", ""),
                        "score": doc.get("score", 0),
                    }
                )

        return sources

    # 保存工具调用日志：把参数、结果、状态、错误和耗时写入 tool_call_logs 表
    def _save_tool_call_logs(self, run_id, session_id: str, trace: dict):
        for tool_call in trace.get("tool_calls", []):
            result = tool_call.get("result", {})
            error = None
            status = "success"
            started_at = tool_call.get("started_at")
            ended_at = tool_call.get("ended_at")
            duration_ms = tool_call.get("duration_ms")

            if isinstance(result, dict):
                error = result.get("error_code") or result.get("error") or None
                error = error or None
                status = result.get("status") or ("failed" if error else "success")
                started_at = started_at or result.get("started_at")
                ended_at = ended_at or result.get("ended_at")
                duration_ms = (
                    duration_ms
                    if duration_ms is not None
                    else result.get("duration_ms")
                )

            save_tool_call(
                run_id=run_id,
                session_id=session_id,
                tool_name=tool_call.get("name", ""),
                arguments=tool_call.get("args", {}),
                result=result,
                status=status,
                error=error,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
            )

    # 根据工具调用结果推断本次 Agent 的业务状态，比如 answered、no_answer、pending_review
    def _infer_status(self, trace: dict) -> str:
        for tool_call in trace.get("tool_calls", []):
            if tool_call.get("name") == "create_ticket":
                result = tool_call.get("result", {})
                if isinstance(result, dict) and result.get("ok") is False:
                    return result.get("status") or "tool_error"
                ticket = result.get("ticket", {}) if isinstance(result, dict) else {}
                return ticket.get("status", "ticket_created")

        for tool_call in trace.get("tool_calls", []):
            if tool_call.get("name") == "search_knowledge_base":
                result = tool_call.get("result", {})
                if result.get("unavailable") is True or result.get("status") == "unavailable":
                    return "rag_unavailable"
                if result.get("found") is False:
                    return "no_answer"

        return "answered"

    # 保存 Agent run 主记录：把 Trace 中可复盘的观测指标沉淀到 agent_runs 表。
    def _save_agent_run_record(
        self,
        run_id: str,
        request: ChatRequest,
        answer: str | None,
        status: str,
        error: str | None,
        started_at: str,
        ended_at: str,
        trace: dict,
        failure_type: str | None = None,
    ):
        observability = self._build_run_observability(
            trace=trace,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            failure_type=failure_type,
            error=error,
        )

        save_agent_run(
            run_id=run_id,
            session_id=request.session_id,
            user_id=request.user_id,
            input_text=request.message,
            output_text=answer,
            status=status,
            error=error,
            started_at=started_at,
            ended_at=ended_at,
            model_name=self.model_name,
            model_provider=self.model_provider,
            **observability,
        )

    # 从 Trace 推导本次 run 的 RAG、工具、工单和失败类型指标。
    def _build_run_observability(
        self,
        trace: dict,
        status: str,
        started_at: str,
        ended_at: str,
        failure_type: str | None = None,
        error: str | None = None,
    ) -> dict:
        tool_calls = trace.get("tool_calls", [])
        rag_hit = None
        rag_top_score = None
        ticket_created = False

        for tool_call in tool_calls:
            name = tool_call.get("name")
            result = tool_call.get("result", {})

            if name == "create_ticket" and isinstance(result, dict):
                ticket_created = bool(result.get("created") or result.get("ticket"))

            if name != "search_knowledge_base" or not isinstance(result, dict):
                continue

            found = result.get("found")
            if found is True:
                rag_hit = True
            elif rag_hit is None and found is False:
                rag_hit = False

            for doc in result.get("results", []):
                score = doc.get("score")
                if score is None:
                    continue
                score = float(score)
                if rag_top_score is None or score > rag_top_score:
                    rag_top_score = score

        return {
            "duration_ms": self._duration_ms(started_at, ended_at),
            "failure_type": failure_type or self._infer_failure_type(status, trace, error),
            "rag_hit": rag_hit,
            "rag_top_score": rag_top_score,
            "tool_count": len(tool_calls),
            "ticket_created": ticket_created,
        }

    # 按状态和工具结果归类失败/兜底类型，方便复盘和面试讲解。
    def _infer_failure_type(self, status: str, trace: dict, error: str | None) -> str | None:
        if error:
            return "model_error"

        for tool_call in trace.get("tool_calls", []):
            result = tool_call.get("result", {})
            if not isinstance(result, dict):
                continue

            error_code = result.get("error_code") or result.get("error")
            if not error_code:
                continue

            if error_code == "rag_unavailable":
                return "rag_unavailable"
            if error_code == "model_parse_error":
                return "model_parse_error"
            return "tool_error"

        if status == "pending_review":
            return "high_risk_review"
        if status == "no_answer":
            return "rag_no_hit"
        if status == "rag_unavailable":
            return "rag_unavailable"
        if status == "failed":
            return "model_error"

        return None

    # 计算一次 run 总耗时；遇到异常时间格式时返回 None，不影响主流程。
    def _duration_ms(self, started_at: str, ended_at: str) -> int | None:
        try:
            started = datetime.fromisoformat(started_at)
            ended = datetime.fromisoformat(ended_at)
        except ValueError:
            return None

        return int((ended - started).total_seconds() * 1000)

    # 高风险人工审核兜底：规则命中且 Agent 没有创建工单时，强制创建 pending_review 工单。
    def _create_high_risk_ticket_if_needed(
        self,
        request: ChatRequest,
        trace: dict,
    ) -> dict | None:
        risk = detect_risk(request.message)

        if risk["risk_level"] != "high":
            return None

        has_ticket = any(
            tool_call.get("name") == "create_ticket"
            for tool_call in trace.get("tool_calls", [])
        )

        if has_ticket:
            return None

        description = (
            f"{request.message}\n\n"
            f"进入人工审核原因：{risk['reason']}\n"
            f"命中关键词：{risk['matched_keyword']}"
        )

        ticket_args = {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "title": "高风险问题人工审核",
            "description": description,
            "priority": "high",
            "risk_level": risk["risk_level"],
            "risk_reason": risk["reason"],
            "matched_keyword": risk["matched_keyword"],
        }

        result_text = create_ticket.invoke(ticket_args)
        #把 JSON 字符串转成 Python 字典dict
        result = self._parse_tool_result(result_text)
        ticket_id = result.get("ticket", {}).get("ticket_id", "")

        answer = (
            f"这个问题需要人工审核，已为您创建工单：{ticket_id}，"
            f"客服会继续跟进处理。"
        )

        return {
            "answer": answer,
            "tool_call": {
                "id": "fallback_create_ticket",
                "name": "create_ticket",
                "args": ticket_args,
                "result": result,
            },
        }
