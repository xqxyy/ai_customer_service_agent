"""
转换公开客服数据集为项目统一格式

这个脚本读取 data/external/ 下的原始 JSONL，并生成：
1. data/generated/public_tickets.jsonl：Tobi 工单标准化结果，可写入 tickets/messages
2. data/generated/public_bitext_intents.jsonl：Bitext 问句标准化结果，可生成 Agent eval
3. data/generated/public_data_report.json：本次转换的统计报告

生成目录已被 .gitignore 忽略，避免把大数据误提交。

运行示例：
    python -m scripts.convert_public_data
    python -m scripts.convert_public_data --tobi-limit 10000 --bitext-limit 5000
"""

from __future__ import annotations

import argparse

from scripts.public_data_utils import (
    BITEXT_RAW_FILE,
    PUBLIC_DATA_REPORT_FILE,
    PUBLIC_INTENTS_FILE,
    PUBLIC_TICKETS_FILE,
    TOBI_RAW_FILE,
    clean_text,
    collect_tags,
    detect_public_risk,
    first_text,
    infer_expected_tools,
    normalize_priority,
    read_jsonl,
    stable_external_id,
    write_json,
    write_jsonl,
)


# 把 Tobi 工单行转换成当前项目 tickets 表和 seed 脚本能理解的统一结构。
def normalize_tobi_row(index: int, row: dict) -> dict:
    subject = first_text(row, ["subject", "title", "Subject"])
    body = first_text(row, ["body", "message", "text", "description", "Body"])
    answer = first_text(row, ["answer", "response", "reply", "Answer"])
    category = first_text(row, ["type", "category", "intent", "Type"])
    queue = first_text(row, ["queue", "department", "Queue"])
    language = first_text(row, ["language", "lang", "Language"])
    tags = collect_tags(row)
    risk = detect_public_risk(subject, body, category, queue, " ".join(tags))

    return {
        "source_dataset": "tobi_customer_support_tickets",
        "external_id": stable_external_id("tobi", index, row),
        "title": subject or body[:80] or f"Public ticket {index}",
        "description": body or subject,
        "answer": answer,
        "priority": normalize_priority(first_text(row, ["priority", "Priority"])),
        "category": category,
        "queue": queue,
        "language": language,
        "tags": tags,
        "risk_level": risk["risk_level"],
        "risk_reason": risk["risk_reason"],
        "matched_keyword": risk["matched_keyword"],
    }


# 把 Bitext 行转换成评估生成脚本可使用的统一结构。
def normalize_bitext_row(index: int, row: dict) -> dict:
    instruction = first_text(row, ["instruction", "question", "utterance", "text"])
    response = first_text(row, ["response", "answer", "completion"])
    category = first_text(row, ["category", "Category"])
    intent = first_text(row, ["intent", "Intent"])
    expected_tools = infer_expected_tools(instruction, category=category, intent=intent)

    return {
        "source_dataset": "bitext_customer_support",
        "external_id": stable_external_id("bitext", index, row),
        "question": instruction,
        "reference_answer": response,
        "category": category,
        "intent": intent,
        "expected_tools": expected_tools,
    }


# 转换 Tobi 数据集；跳过没有正文的空记录，避免污染工单表。
def convert_tobi(limit: int | None) -> dict:
    if not TOBI_RAW_FILE.exists():
        return {
            "dataset": "tobi_customer_support_tickets",
            "input_exists": False,
            "written": 0,
            "output": str(PUBLIC_TICKETS_FILE),
        }

    def rows():
        for index, row in enumerate(read_jsonl(TOBI_RAW_FILE, limit=limit), start=1):
            normalized = normalize_tobi_row(index, row)
            if clean_text(normalized["description"]):
                yield normalized

    written = write_jsonl(PUBLIC_TICKETS_FILE, rows())
    return {
        "dataset": "tobi_customer_support_tickets",
        "input_exists": True,
        "written": written,
        "output": str(PUBLIC_TICKETS_FILE),
    }


# 转换 Bitext 数据集；跳过没有 question 的记录，避免生成无意义评估用例。
def convert_bitext(limit: int | None) -> dict:
    if not BITEXT_RAW_FILE.exists():
        return {
            "dataset": "bitext_customer_support",
            "input_exists": False,
            "written": 0,
            "output": str(PUBLIC_INTENTS_FILE),
        }

    def rows():
        for index, row in enumerate(read_jsonl(BITEXT_RAW_FILE, limit=limit), start=1):
            normalized = normalize_bitext_row(index, row)
            if clean_text(normalized["question"]):
                yield normalized

    written = write_jsonl(PUBLIC_INTENTS_FILE, rows())
    return {
        "dataset": "bitext_customer_support",
        "input_exists": True,
        "written": written,
        "output": str(PUBLIC_INTENTS_FILE),
    }


# 命令行参数：允许先用 limit 小规模验证，再全量转换。
def parse_args():
    parser = argparse.ArgumentParser(description="转换公开客服数据集为项目统一格式")
    parser.add_argument("--tobi-limit", type=int, default=0, help="Tobi 最多转换多少行；0 表示全部")
    parser.add_argument("--bitext-limit", type=int, default=0, help="Bitext 最多转换多少行；0 表示全部")
    return parser.parse_args()


# 脚本入口：转换两个数据集并输出报告。
def main():
    args = parse_args()
    report = {
        "tobi": convert_tobi(args.tobi_limit or None),
        "bitext": convert_bitext(args.bitext_limit or None),
    }

    write_json(PUBLIC_DATA_REPORT_FILE, report)
    print(f"[report] {PUBLIC_DATA_REPORT_FILE}")
    print(report)


if __name__ == "__main__":
    main()
