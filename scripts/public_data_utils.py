"""
公开客服数据集处理公共工具

这个文件把下载、转换、seed、eval 生成脚本里会重复用到的路径、JSONL 读写、
文本清洗、字段映射和简单规则集中放在一起。这样后续新增别的公开数据集时，
只需要复用这些函数，不必在多个脚本里复制一套解析逻辑。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


# 项目根目录：scripts/ 的上一级就是项目根，用它拼出所有数据路径。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DIR = DATA_DIR / "external"
GENERATED_DIR = DATA_DIR / "generated"
PUBLIC_SAMPLES_DIR = DATA_DIR / "public_samples"

# 原始下载文件：这些文件较大，已经在 .gitignore 中忽略。
TOBI_RAW_FILE = EXTERNAL_DIR / "tobi_customer_support_tickets.jsonl"
BITEXT_RAW_FILE = EXTERNAL_DIR / "bitext_customer_support.jsonl"

# 转换后文件：这些文件也由脚本生成，默认不提交。
PUBLIC_TICKETS_FILE = GENERATED_DIR / "public_tickets.jsonl"
PUBLIC_INTENTS_FILE = GENERATED_DIR / "public_bitext_intents.jsonl"
PUBLIC_AGENT_EVAL_FILE = GENERATED_DIR / "public_customer_service_eval.json"
PUBLIC_DATA_REPORT_FILE = GENERATED_DIR / "public_data_report.json"


# 公开数据集配置：脚本直接读取 Hugging Face 仓库里的 CSV 文件，避免依赖 datasets 构建流程。
DATASET_CONFIGS = {
    "tobi": {
        "hf_id": "Tobi-Bueck/customer-support-tickets",
        "split": "train",
        "raw_file": TOBI_RAW_FILE,
        "raw_urls": [
            "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/aa_dataset-tickets-multi-lang-5-2-50-version.csv",
            "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/dataset-tickets-multi-lang-4-20k.csv",
            "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/dataset-tickets-german_normalized_50_5_2.csv",
        ],
        "source_dataset": "tobi_customer_support_tickets",
        "license": "CC-BY-NC-4.0",
        "url": "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets",
    },
    "bitext": {
        "hf_id": "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "split": "train",
        "raw_file": BITEXT_RAW_FILE,
        "raw_urls": [
            "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/resolve/main/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv",
        ],
        "source_dataset": "bitext_customer_support",
        "license": "CDLA-Sharing-1.0",
        "url": "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset",
    },
}


# 英文公开工单中常见的高风险表达；和中文 risk_service 的定位一致，都是后端兜底规则。
PUBLIC_HIGH_RISK_RULES = [
    ("complaint", "用户投诉需要人工审核"),
    ("compensation", "赔偿不能由 AI 直接承诺"),
    ("lawyer", "法律风险需要人工处理"),
    ("legal", "法律风险需要人工处理"),
    ("lawsuit", "法律风险需要人工处理"),
    ("sue", "法律风险需要人工处理"),
    ("privacy", "隐私问题需要人工处理"),
    ("gdpr", "隐私问题需要人工处理"),
    ("data leak", "隐私泄露风险需要人工处理"),
    ("data breach", "隐私泄露风险需要人工处理"),
    ("account hacked", "账号安全问题需要人工核验"),
    ("fraud", "欺诈风险需要人工核验"),
    ("chargeback", "支付争议需要人工处理"),
    ("human agent", "用户明确要求人工处理"),
]


# 这些关键词用于把 Bitext 的公开问句粗略映射到当前项目的工具预期。
ORDER_TOOL_KEYWORDS = [
    "where is my order",
    "track my order",
    "tracking",
    "order status",
    "delivery status",
    "shipment status",
]
CUSTOMER_TOOL_KEYWORDS = [
    "my account",
    "account details",
    "profile",
    "membership",
    "vip",
    "customer information",
]
KNOWLEDGE_TOOL_KEYWORDS = [
    "refund",
    "return",
    "exchange",
    "shipping",
    "delivery",
    "invoice",
    "payment",
    "coupon",
    "cancel",
    "warranty",
    "policy",
]


# 创建目录，保证脚本第一次运行时不会因为目录不存在而失败。
def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


# 清洗任意字段为单行文本，避免公开数据里的换行、重复空格影响 JSONL 和数据库展示。
def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    return re.sub(r"\s+", " ", text).strip()


# 从一行原始数据里按候选字段名取第一个非空文本。
def first_text(row: dict, keys: Iterable[str]) -> str:
    for key in keys:
        value = clean_text(row.get(key))
        if value:
            return value
    return ""


# 读取 JSONL 文件，limit 为 None 或 0 时读取全部。
def read_jsonl(path: Path, limit: int | None = None):
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            yield json.loads(line)
            count += 1
            if limit and count >= limit:
                break


# 写 JSONL 文件，返回写入条数，方便脚本打印报告。
def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    ensure_parent(path)
    count = 0
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# 写普通 JSON 文件，统一 UTF-8 和缩进格式。
def write_json(path: Path, payload) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# 构造稳定外部 ID：优先用数据自带 id，没有就用行号和内容 hash，保证重复运行 seed 不重复插入。
def stable_external_id(prefix: str, index: int, row: dict) -> str:
    for key in ("id", "ticket_id", "conversation_id", "thread_id"):
        value = clean_text(row.get(key))
        if value:
            return f"{prefix}-{value}"

    digest = hashlib.sha1(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


# 把公开数据里的优先级映射到当前工单系统使用的 low/normal/high。
def normalize_priority(value: str) -> str:
    text = clean_text(value).lower()
    if text in {"high", "urgent", "critical"}:
        return "high"
    if text in {"low", "minor"}:
        return "low"
    return "normal"


# 提取 tag_1/tag_2/... 或 tags 字段，统一成字符串列表。
def collect_tags(row: dict) -> list[str]:
    tags = []
    raw_tags = row.get("tags")

    if isinstance(raw_tags, list):
        tags.extend(clean_text(item) for item in raw_tags)
    elif clean_text(raw_tags):
        tags.extend(part.strip() for part in clean_text(raw_tags).split(","))

    for key, value in row.items():
        if key.lower().startswith("tag"):
            tag = clean_text(value)
            if tag:
                tags.append(tag)

    seen = set()
    unique_tags = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    return unique_tags


# 公开数据的高风险识别：用于转换数据和生成 eval 预期，不替代线上 risk_service。
def detect_public_risk(*texts) -> dict:
    merged = " ".join(clean_text(text) for text in texts).lower()
    for keyword, reason in PUBLIC_HIGH_RISK_RULES:
        if keyword in merged:
            return {
                "risk_level": "high",
                "risk_reason": reason,
                "matched_keyword": keyword,
            }

    return {
        "risk_level": "normal",
        "risk_reason": "",
        "matched_keyword": "",
    }


# 根据公开问句粗略推断当前 Agent 应该调用哪个工具；只做评估集初筛，人工仍可二次筛选。
def infer_expected_tools(question: str, category: str = "", intent: str = "") -> list[str]:
    text = " ".join([question, category, intent]).lower()

    if detect_public_risk(text)["risk_level"] == "high":
        return ["create_ticket"]

    if any(keyword in text for keyword in ORDER_TOOL_KEYWORDS):
        return ["get_latest_order"]

    if any(keyword in text for keyword in CUSTOMER_TOOL_KEYWORDS):
        return ["get_customer_info"]

    if any(keyword in text for keyword in KNOWLEDGE_TOOL_KEYWORDS):
        return ["search_knowledge_base"]

    return []
