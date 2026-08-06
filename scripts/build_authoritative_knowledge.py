"""
构建中国国内权威来源 RAG 文档

这个脚本读取 data/knowledge_base/authoritative_sources.json，把其中登记的官方来源、
客服摘要、处理步骤、边界和升级条件生成 markdown 文档，并自动合并到 sources.json。

它的设计目的不是复制官方网页全文，而是把权威资料整理成适合客服 Agent 检索的
“处理参考卡片”：每张卡片保留来源 URL、适用范围、客服处理步骤和禁止承诺边界。
这样既能扩充正式知识库，也能降低直接搬运网页正文带来的版权和过期风险。

运行方式：
    python -m scripts.build_authoritative_knowledge
"""

from __future__ import annotations

import json
from pathlib import Path


# 项目根目录和知识库关键文件路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = PROJECT_ROOT / "data" / "knowledge_base" / "authoritative_sources.json"
SOURCES_FILE = PROJECT_ROOT / "data" / "knowledge_base" / "sources.json"


# 读取 JSON 文件，统一封装便于后续扩展校验逻辑
def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# 写 JSON 文件，保留中文并使用稳定缩进，减少 sources.json 的无意义 diff
def write_json(path: Path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# 把列表渲染成 markdown bullet；空列表也返回一条占位，避免生成空章节
def render_bullets(items: list[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join(f"- {item}" for item in items)


# 生成来源列表：每条保留发布机构、资料类型和 URL，方便 RAG 回答时追溯依据
def render_sources(authority_sources: list[dict]) -> str:
    lines = []
    for source in authority_sources:
        name = source.get("name", "")
        publisher = source.get("publisher", "")
        source_type = source.get("source_type", "")
        url = source.get("url", "")
        lines.append(f"- {name}（{publisher}，{source_type}）：{url}")
    return "\n".join(lines)


# 把一条权威来源登记转换成 markdown 文档内容
def build_markdown(item: dict) -> str:
    return f"""# {item["title"]}

## 资料定位

- 文档 ID：{item["doc_id"]}
- 适用地区：{item.get("jurisdiction", "未标注")}
- 业务领域：{item.get("business_area", "未标注")}
- 风险等级：{item.get("risk_level", "normal")}
- 更新说明：{item.get("update_note", "需随官方资料更新")}

## 权威来源

{render_sources(item.get("authority_sources", []))}

## 客服处理摘要

{render_bullets(item.get("customer_service_summary", []))}

## 标准处理步骤

{render_bullets(item.get("standard_handling", []))}

## 回答边界

{render_bullets(item.get("answer_boundaries", []))}

## 人工升级触发条件

{render_bullets(item.get("escalation_triggers", []))}

## 典型用户问题

{render_bullets(item.get("sample_questions", []))}

## 使用提醒

- 本文档是面向客服 Agent 的权威资料摘要，不是法律意见。
- 回答用户时应结合订单、商品、地区、平台规则和人工审核结果。
- 涉及投诉、赔偿、隐私、法律、监管举报等高风险事项时，应创建人工审核工单。
"""


# 写入 markdown 文件，并返回 sources.json 需要的 source 条目
def write_markdown_and_build_source(item: dict) -> dict:
    output_path = PROJECT_ROOT / item["source_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(item), encoding="utf-8")

    return {
        "doc_id": item["doc_id"],
        "title": item["title"],
        "source_path": item["source_path"],
        "doc_type": "markdown",
        "business_area": item.get("business_area", "权威资料"),
        "risk_level": item.get("risk_level", "normal"),
        "need_ocr": False,
        "source_kind": "authoritative_reference",
        "jurisdiction": item.get("jurisdiction", ""),
    }


# 合并 sources.json：同 doc_id 覆盖旧项，其他原有知识库保持不动
def merge_sources(existing_sources: list[dict], generated_sources: list[dict]) -> list[dict]:
    generated_by_id = {
        source["doc_id"]: source
        for source in generated_sources
    }

    merged = []
    seen = set()
    for source in existing_sources:
        doc_id = source["doc_id"]
        merged.append(generated_by_id.get(doc_id, source))
        seen.add(doc_id)

    for source in generated_sources:
        if source["doc_id"] not in seen:
            merged.append(source)

    return merged


# 脚本入口：生成 markdown 文档，并把它们登记进 sources.json
def main():
    registry = read_json(REGISTRY_FILE)
    existing_sources = read_json(SOURCES_FILE)

    generated_sources = [
        write_markdown_and_build_source(item)
        for item in registry
    ]
    merged_sources = merge_sources(existing_sources, generated_sources)
    write_json(SOURCES_FILE, merged_sources)

    print(f"Generated authoritative docs: {len(generated_sources)}")
    print(f"Updated sources: {SOURCES_FILE}")


if __name__ == "__main__":
    main()
