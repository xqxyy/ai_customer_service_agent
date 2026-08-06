"""
已处理知识文档读取模块

这个文件负责读取 data/processed/documents.jsonl，并提供给工作台展示当前知识库包含哪些文档
存在的原因是：在线问答使用 Milvus 检索，前端工作台仍然需要一个轻量入口来展示“当前项目加载了哪些知识资料”
"""

import json
from pathlib import Path


# 项目根目录和预处理文档路径：脚本生成 documents.jsonl 后，这里负责读取
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed" / "documents.jsonl"


# 读取预处理后的文档列表；文件不存在时返回空列表，避免工作台启动失败
def load_processed_documents() -> list[dict]:
    if not PROCESSED_FILE.exists():
        return []

    documents = []
    with PROCESSED_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                documents.append(json.loads(line))

    return documents
