"""读取最近一次评估报告，供工作台展示。

评估脚本负责生成 JSON 报告；FastAPI 只读取报告摘要，不在接口请求里实时跑评估，
避免工作台刷新时触发模型调用或 Milvus 大量检索。
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = PROJECT_ROOT / "data" / "processed"
RAG_REPORT_FILE = REPORT_DIR / "rag_eval_report.json"
AGENT_REPORT_FILE = REPORT_DIR / "customer_service_eval_report.json"
RAG_EVAL_FILE = PROJECT_ROOT / "data" / "eval" / "rag_eval.json"
AGENT_EVAL_FILE = PROJECT_ROOT / "backend" / "app" / "data" / "eval" / "customer_service_eval.json"


def _case_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return 0


def _load_report(path: Path, eval_file: Path) -> dict:
    if not path.exists():
        return {
            "status": "not_run",
            "report_file": str(path.relative_to(PROJECT_ROOT)),
            "case_count": _case_count(eval_file),
            "summary": {},
            "generated_at": None,
        }

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {
            "status": "invalid",
            "report_file": str(path.relative_to(PROJECT_ROOT)),
            "case_count": _case_count(eval_file),
            "summary": {},
            "generated_at": None,
            "error": str(error),
        }

    summary = report.get("summary", {})
    return {
        "status": "ready",
        "report_file": str(path.relative_to(PROJECT_ROOT)),
        "case_count": summary.get("total", _case_count(eval_file)),
        "summary": summary,
        "generated_at": report.get("generated_at"),
    }


def load_eval_reports() -> dict:
    return {
        "rag": _load_report(RAG_REPORT_FILE, RAG_EVAL_FILE),
        "agent": _load_report(AGENT_REPORT_FILE, AGENT_EVAL_FILE),
    }
