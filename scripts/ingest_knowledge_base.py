"""
RAG 向量入库脚本

这个脚本读取 data/processed/chunks.jsonl，调用 Embedding 模型生成向量，然后重建并写入 Milvus collection
存在的原因是：知识库更新应该通过离线脚本完成，在线 /chat 请求只负责检索，避免用户请求里做耗时的入库操作

运行方式：
    python -m scripts.ingest_knowledge_base
"""

import json
from datetime import datetime
from pathlib import Path

from backend.app.rag.retriever import (
    EMBED_DIM,
    MILVUS_COLLECTION_NAME,
    MILVUS_TIMEOUT_SECONDS,
    create_collection,
    get_client,
    get_embedding_model,
)


# 输入输出路径：chunks.jsonl 是入库数据，ingest_report.json 记录本次入库摘要
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"
SOURCES_FILE = PROJECT_ROOT / "data" / "knowledge_base" / "sources.json"
DOCUMENTS_FILE = PROJECT_ROOT / "data" / "processed" / "documents.jsonl"
REPORT_FILE = PROJECT_ROOT / "data" / "processed" / "ingest_report.json"
OCR_TEXT_DIR = PROJECT_ROOT / "data" / "processed" / "ocr_texts"


# 读取 JSONL 文件：入库前加载已经切好的知识片段
def read_jsonl(path: Path) -> list[dict]:
    rows = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))

    return rows


# 写入库报告：记录文档数、切块数和被跳过的 OCR 文档，方便排查数据是否完整
def write_ingest_report(
    total_sources: int,
    prepared_docs: int,
    chunks: int,
    skipped_ocr: list[str],
):
    report = {
        "created_at": datetime.now().isoformat(),
        "total_sources": total_sources,
        "prepared_docs": prepared_docs,
        "chunks": chunks,
        "skipped_ocr": skipped_ocr,
    }

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# 批量写入 Milvus：先生成向量，再把向量和文档元数据一起插入 collection
def insert_chunks(client, chunks: list[dict]):
    embedding_model = get_embedding_model()

    vectors = embedding_model.embed_documents([chunk["content"] for chunk in chunks])

    data = []
    for index, chunk in enumerate(chunks):
        vector = vectors[index]

        if len(vector) != EMBED_DIM:
            raise ValueError(
                f"Embedding dimension mismatch: expected {EMBED_DIM}, got {len(vector)}"
            )

        data.append(
            {
                "id": index + 1,
                "vector": vector,
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "source": chunk["source"],
                "source_path": chunk.get("source_path", ""),
                "doc_type": chunk.get("doc_type", ""),
                "business_area": chunk.get("business_area", ""),
                "risk_level": chunk.get("risk_level", "normal"),
                "content": chunk["content"],
                "chunk_id": chunk["chunk_id"],
            }
        )

    if data:
        client.insert(
            collection_name=MILVUS_COLLECTION_NAME,
            data=data,
            timeout=MILVUS_TIMEOUT_SECONDS,
        )
        client.flush(
            collection_name=MILVUS_COLLECTION_NAME,
            timeout=MILVUS_TIMEOUT_SECONDS,
        )


# 脚本入口：重建 collection、插入切块、输出入库报告
def main():
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    documents = read_jsonl(DOCUMENTS_FILE)
    chunks = read_jsonl(CHUNKS_FILE)

    client = get_client()
    create_collection(client)
    insert_chunks(client, chunks)

    skipped_ocr = [
        source["doc_id"]
        for source in sources
        if source.get("need_ocr")
        and not (OCR_TEXT_DIR / f"{source['doc_id']}.txt").exists()
    ]

    write_ingest_report(
        total_sources=len(sources),
        prepared_docs=len(documents),
        chunks=len(chunks),
        skipped_ocr=skipped_ocr,
    )

    print(f"Ingested {len(chunks)} chunks into Milvus.")


if __name__ == "__main__":
    main()
