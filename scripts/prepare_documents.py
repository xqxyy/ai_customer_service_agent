"""
RAG 文档预处理脚本

这个脚本读取 data/knowledge_base/sources.json 中登记的知识源，调用对应 loader 读取内容，最后写入 data/processed/documents.jsonl
它存在的原因是：知识库原始资料格式很多，需要先统一成标准 document，后面才能切块、向量化和入库

运行方式：
    python -m scripts.prepare_documents
"""

import json
from pathlib import Path

from backend.app.rag.loaders import load_source_content


# 输入输出路径：sources.json 是知识源清单，documents.jsonl 是标准化后的文档
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = PROJECT_ROOT / "data" / "knowledge_base" / "sources.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "documents.jsonl"
OCR_TEXT_DIR = PROJECT_ROOT / "data" / "processed" / "ocr_texts"


# 读取知识源目录：每一项描述一份知识库文件及其元数据
def load_sources() -> list[dict]:
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


# 把一条 source 元数据转换成标准 document；扫描 PDF 优先使用 OCR 生成的文本
def build_document(source: dict) -> dict | None:
    if source.get("need_ocr"):
        ocr_text_path = OCR_TEXT_DIR / f"{source['doc_id']}.txt"
        if not ocr_text_path.exists():
            print(f"SKIP OCR document: {source['doc_id']}")
            return None

        content = ocr_text_path.read_text(encoding="utf-8").strip()
    else:
        content = load_source_content(source)

    if not content.strip():
        return None

    return {
        "doc_id": source["doc_id"],
        "title": source["title"],
        "source": Path(source["source_path"]).name,
        "source_path": source["source_path"],
        "doc_type": source["doc_type"],
        "content": content,
        "metadata": {
            "business_area": source.get("business_area"),
            "risk_level": source.get("risk_level"),
            "need_ocr": source.get("need_ocr", False),
            # source_kind 用来区分项目自造示例、公开数据、权威资料等不同来源类型，便于后续筛选和解释。
            "source_kind": source.get("source_kind", "project_sample"),
            # jurisdiction 标记资料适用地区；先支持中国大陆，后续可扩展到省市或海外地区。
            "jurisdiction": source.get("jurisdiction", ""),
        },
    }


# 写 JSONL 文件：一行一个 JSON 对象，方便后续流式读取和调试
def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


# 脚本入口：遍历所有 source，生成标准化 document 文件
def main():
    documents = []

    for source in load_sources():
        document = build_document(source)
        if document:
            documents.append(document)

    write_jsonl(OUTPUT_FILE, documents)
    print(f"Prepared {len(documents)} documents: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
