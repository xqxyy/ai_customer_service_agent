"""
客服 Agent 端到端评估脚本

这个文件读取 backend/app/data/eval/customer_service_eval.json，逐条调用 CustomerServiceAgent，
再从数据库按 run_id 读取工具调用日志和引用来源，验证 Agent 是否按预期调用工具、
是否命中指定知识文档、是否正确进入人工审核或无答案状态。
存在的原因是：Agent 行为具有不确定性，工程项目必须有可重复评估脚本来发现回归

运行方式：
    python -m backend.app.evals.run_customer_service_eval
"""

import argparse
import json
from pathlib import Path

from backend.app.agents.customer_service_agent import CustomerServiceAgent
from backend.app.db.session import (
    init_db,
    list_message_sources_by_run_id,
    list_tool_calls_by_run_id,
)
from backend.app.schemas.chat import ChatRequest


# 评估集路径：每条用例会声明预期工具、禁止工具、预期来源和预期状态
EVAL_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "eval"
    / "customer_service_eval.json"
)


# 读取 Agent 评估用例；默认读项目小验证集，也可以用 --eval-file 指向公开数据生成的大验证集
def load_eval_cases(eval_file: Path = EVAL_FILE) -> list[dict]:
    with eval_file.open("r", encoding="utf-8") as file:
        return json.load(file)


# 检查 expected 里的所有元素是否都出现在 actual 里
def contains_all(expected: list[str], actual: list[str]) -> bool:
    return all(item in actual for item in expected)


# 检查 forbidden 里的元素是否都没有出现在 actual 里，避免误调用工具
def contains_none(forbidden: list[str], actual: list[str]) -> bool:
    return all(item not in actual for item in forbidden)


# 执行单条 Agent 评估：调用 Agent 后用数据库 Trace 对比预期结果
def evaluate_case(agent: CustomerServiceAgent, case: dict) -> dict:
    request = ChatRequest(
        session_id=f"eval-{case['id']}",
        user_id=case.get("user_id", "user-001"),
        message=case["question"],
    )

    response = agent.run(request)

    tool_calls = list_tool_calls_by_run_id(response.run_id)
    actual_tools = [
        tool_call["tool_name"]
        for tool_call in tool_calls
        if tool_call.get("tool_name")
    ]

    actual_sources = list_message_sources_by_run_id(response.run_id)
    actual_source_ids = [
        source.get("doc_id")
        for source in actual_sources
        if source.get("doc_id")
    ]

    expected_tools = case.get("expected_tools", [])
    forbidden_tools = case.get("forbidden_tools", [])
    expected_sources = case.get("expected_sources", [])
    expected_status = case.get("expected_status")
    should_answer = case.get("should_answer")

    expected_tools_ok = contains_all(expected_tools, actual_tools)
    forbidden_tools_ok = contains_none(forbidden_tools, actual_tools)
    sources_ok = contains_all(expected_sources, actual_source_ids)
    status_ok = expected_status is None or expected_status == response.status

    answer_has_text = bool(response.answer.strip())

    if should_answer is None:
        should_answer_ok = True
    elif should_answer:
        should_answer_ok = answer_has_text and response.status == "answered"
    else:
        should_answer_ok = response.status != "answered"

    passed = (
        expected_tools_ok
        and forbidden_tools_ok
        and sources_ok
        and status_ok
        and should_answer_ok
    )

    return {
        "id": case["id"],
        "passed": passed,
        "question": case["question"],
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "forbidden_tools": forbidden_tools,
        "expected_sources": expected_sources,
        "actual_source_ids": actual_source_ids,
        "actual_sources": actual_sources,
        "expected_status": expected_status,
        "actual_status": response.status,
        "should_answer": should_answer,
        "answer": response.answer,
        "checks": {
            "expected_tools_ok": expected_tools_ok,
            "forbidden_tools_ok": forbidden_tools_ok,
            "sources_ok": sources_ok,
            "status_ok": status_ok,
            "should_answer_ok": should_answer_ok,
        },
    }


# 打印评估报告：失败用例会输出实际回答，方便定位 Agent 行为变化
def print_report(results: list[dict]):
    passed_count = sum(1 for result in results if result["passed"])
    total_count = len(results)

    print("\n=== Customer Service Agent Eval ===")
    print(f"Passed: {passed_count}/{total_count}\n")

    for result in results:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"[{mark}] {result['id']} - {result['question']}")
        print(f"  expected_tools:   {result['expected_tools']}")
        print(f"  actual_tools:     {result['actual_tools']}")
        print(f"  forbidden_tools:  {result['forbidden_tools']}")
        print(f"  expected_sources: {result['expected_sources']}")
        print(f"  actual_source_ids:{result['actual_source_ids']}")
        print(f"  expected_status:  {result['expected_status']}")
        print(f"  actual_status:    {result['actual_status']}")
        print(f"  should_answer:    {result['should_answer']}")
        print(f"  checks:           {result['checks']}")

        if not result["passed"]:
            print(f"  answer: {result['answer']}")

        print()


# 解析命令行参数，让公开数据生成的评估集可以单独运行，不覆盖手写核心评估集
def parse_args():
    parser = argparse.ArgumentParser(description="运行客服 Agent 端到端评估")
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=EVAL_FILE,
        help="评估集 JSON 路径，默认使用 backend/app/data/eval/customer_service_eval.json",
    )
    return parser.parse_args()


# 脚本入口：初始化数据库、创建 Agent、执行全部评估用例
def main():
    args = parse_args()
    init_db()
    cases = load_eval_cases(args.eval_file)
    agent = CustomerServiceAgent()

    results = []
    for case in cases:
        results.append(evaluate_case(agent, case))

    print_report(results)


if __name__ == "__main__":
    main()
