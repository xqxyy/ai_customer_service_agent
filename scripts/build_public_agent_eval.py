"""
从 Bitext 公开客服数据生成 Agent 大评估集

这个脚本读取 data/generated/public_bitext_intents.jsonl，按简单规则生成当前
CustomerServiceAgent 可以执行的 eval case。生成文件默认写到 data/generated/，
不会覆盖手写核心评估集。

运行示例：
    python -m scripts.build_public_agent_eval --limit 300
    python -m backend.app.evals.run_customer_service_eval --eval-file data/generated/public_customer_service_eval.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.public_data_utils import (
    PUBLIC_AGENT_EVAL_FILE,
    PUBLIC_INTENTS_FILE,
    clean_text,
    read_jsonl,
    write_json,
)


# 把标准化 Bitext 记录转换为 Agent eval case。
def build_case(index: int, record: dict) -> dict:
    expected_tools = record.get("expected_tools") or []
    forbidden_tools = []

    if "create_ticket" not in expected_tools:
        forbidden_tools.append("create_ticket")

    expected_status = "pending_review" if "create_ticket" in expected_tools else None

    return {
        "id": f"public_bitext_{index:05d}",
        "question": clean_text(record.get("question")),
        "expected_tools": expected_tools,
        "forbidden_tools": forbidden_tools,
        "expected_sources": [],
        "expected_status": expected_status,
        "should_answer": None,
        "metadata": {
            "source_dataset": record.get("source_dataset"),
            "external_id": record.get("external_id"),
            "category": record.get("category"),
            "intent": record.get("intent"),
            "reference_answer": record.get("reference_answer"),
        },
    }


# 生成评估集；默认只保留能推断出 expected_tools 的用例，避免验证集太噪。
def build_eval_cases(limit: int | None, include_uncertain: bool) -> list[dict]:
    if not PUBLIC_INTENTS_FILE.exists():
        raise SystemExit(
            f"找不到 {PUBLIC_INTENTS_FILE}。请先运行 python -m scripts.convert_public_data"
        )

    cases = []
    for record in read_jsonl(PUBLIC_INTENTS_FILE):
        if not include_uncertain and not record.get("expected_tools"):
            continue

        case = build_case(len(cases) + 1, record)
        if not case["question"]:
            continue

        cases.append(case)
        if limit and len(cases) >= limit:
            break

    return cases


# 命令行参数：limit 控制评估集规模，include-uncertain 可保留无法推断工具的泛化问题。
def parse_args():
    parser = argparse.ArgumentParser(description="从公开 Bitext 数据生成 Agent eval")
    parser.add_argument("--limit", type=int, default=300, help="最多生成多少条；0 表示全部")
    parser.add_argument(
        "--include-uncertain",
        action="store_true",
        help="保留未推断出 expected_tools 的问题",
    )
    parser.add_argument(
        "--output",
        default=str(PUBLIC_AGENT_EVAL_FILE),
        help="输出 eval JSON 路径",
    )
    return parser.parse_args()


# 脚本入口：生成 JSON 评估集并打印数量。
def main():
    args = parse_args()
    cases = build_eval_cases(
        limit=args.limit or None,
        include_uncertain=args.include_uncertain,
    )
    write_json(Path(args.output), cases)
    print(f"[done] wrote {len(cases)} cases -> {args.output}")


if __name__ == "__main__":
    main()
