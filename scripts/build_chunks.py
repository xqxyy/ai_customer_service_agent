"""
RAG 文档切块脚本

这个脚本读取 data/processed/documents.jsonl，把长文档切成适合向量检索的小片段，并写入 data/processed/chunks.jsonl
存在的原因是：向量检索不适合直接检索整篇长文档，切块可以提高召回精度，也能让最终回答引用更具体的依据片段。

运行方式：
    python -m scripts.build_chunks
"""

import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# 输入输出路径：documents.jsonl 来自 prepare_documents，chunks.jsonl 供入库脚本读取
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_FILE = PROJECT_ROOT / "data" / "processed" / "documents.jsonl"
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"


# 读取 JSONL 文件：用于加载标准文档或切块结果
def read_jsonl(path: Path) -> list[dict]:
    rows = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))

    return rows


# 写 JSONL 文件：保留中文内容，方便人工检查切块质量
def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


# 构建知识片段：用 LangChain 递归切分器保留段落、句号等中文语义边界
def build_chunks(documents: list[dict]) -> list[dict]:
    langchain_docs = [
        Document(
            page_content=document["content"],
            metadata={
                "doc_id": document["doc_id"],
                "title": document["title"],
                "source": document["source"],
                "source_path": document["source_path"],
                "doc_type": document["doc_type"],
                **document.get("metadata", {}),
            },
        )
        for document in documents
    ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=150,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )

    chunks = splitter.split_documents(langchain_docs)

    rows = []
    for index, chunk in enumerate(chunks):
        rows.append(
            {
                "chunk_id": index,
                "doc_id": chunk.metadata.get("doc_id", ""),
                "title": chunk.metadata.get("title", ""),
                "source": chunk.metadata.get("source", ""),
                "source_path": chunk.metadata.get("source_path", ""),
                "doc_type": chunk.metadata.get("doc_type", ""),
                "business_area": chunk.metadata.get("business_area"),
                "risk_level": chunk.metadata.get("risk_level"),
                # 保留来源类型和适用地区，后续入库到 Milvus 后可以用于检索结果解释或区域过滤。
                "source_kind": chunk.metadata.get("source_kind", ""),
                "jurisdiction": chunk.metadata.get("jurisdiction", ""),
                "content": chunk.page_content,
            }
        )

    return rows


# 脚本入口：读取标准文档、切块、写出 chunks.jsonl
def main():
    documents = read_jsonl(DOCUMENTS_FILE)
    chunks = build_chunks(documents)
    write_jsonl(CHUNKS_FILE, chunks)

    print(f"Built {len(chunks)} chunks: {CHUNKS_FILE}")


if __name__ == "__main__":
    main()
