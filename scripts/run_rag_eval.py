"""
RAG 检索评估脚本

这个脚本读取 data/eval/rag_eval.json，用固定问题检查 Milvus 检索是否命中预期文档
存在的原因是：RAG 不是“能搜到东西”就算成功，还要验证 top1/top3 命中率、无答案问题是否被正确过滤，以及阈值是否合适

运行方式：
    python -m scripts.run_rag_eval
"""

import json
from pathlib import Path

from backend.app.rag.retriever import search_documents


# 评估集路径：每条用例包含问题、预期 doc_id，以及是否应该命中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_FILE = PROJECT_ROOT / "data" / "eval" / "rag_eval.json"


# 读取 RAG 评估用例
def load_cases() -> list[dict]:
    return json.loads(EVAL_FILE.read_text(encoding="utf-8"))


# 执行单条评估：检索 top3，判断是否命中预期文档或是否正确无答案
def evaluate_case(case: dict) -> dict:
    results = search_documents(case["question"], top_k=3)
    actual_doc_ids = [item["doc_id"] for item in results]

    expected_doc_ids = case.get("expected_doc_ids", [])
    should_hit = case.get("should_hit", True)

    top1_hit = bool(actual_doc_ids) and actual_doc_ids[0] in expected_doc_ids
    top3_hit = any(doc_id in actual_doc_ids for doc_id in expected_doc_ids)

    if should_hit:
        passed = top3_hit
    else:
        passed = len(actual_doc_ids) == 0

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": passed,
        "expected_doc_ids": expected_doc_ids,
        "actual_doc_ids": actual_doc_ids,
        "should_hit": should_hit,
        "top1_hit": top1_hit,
        "top3_hit": top3_hit,
        "top_score": results[0]["score"] if results else 0,
    }


# 打印评估报告：展示整体通过率、命中率和每条用例的实际命中文档
def print_report(results: list[dict]):
    total = len(results)
    passed = sum(1 for item in results if item["passed"])

    hit_cases = [item for item in results if item["should_hit"]]
    no_hit_cases = [item for item in results if not item["should_hit"]]

    top1_rate = sum(1 for item in hit_cases if item["top1_hit"]) / len(hit_cases)
    top3_rate = sum(1 for item in hit_cases if item["top3_hit"]) / len(hit_cases)
    no_answer_accuracy = sum(1 for item in no_hit_cases if item["passed"]) / len(no_hit_cases)
    avg_top_score = sum(item["top_score"] for item in results) / total

    print("\n=== RAG Eval ===")
    print(f"case_pass_rate: {passed}/{total}")
    print(f"top1_hit_rate: {top1_rate:.2%}")
    print(f"top3_hit_rate: {top3_rate:.2%}")
    print(f"no_answer_accuracy: {no_answer_accuracy:.2%}")
    print(f"avg_top_score: {avg_top_score:.4f}\n")

    for item in results:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"[{mark}] {item['id']} - {item['question']}")
        print(f"  expected_doc_ids: {item['expected_doc_ids']}")
        print(f"  actual_doc_ids:   {item['actual_doc_ids']}")
        print(f"  top_score:        {item['top_score']}")
        print()


# 脚本入口：读取用例、逐条执行、打印汇总报告。
def main():
    cases = load_cases()
    results = [evaluate_case(case) for case in cases]
    print_report(results)


if __name__ == "__main__":
    main()
