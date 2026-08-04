"""
RAG 包标记文件：存放文档加载、检索和知识库读取逻辑

原始知识库文件
  -> sources.json 登记（目前依赖人工）
  -> loaders.py / OCR 读取文本
  -> documents.jsonl
  -> chunks.jsonl
  -> Embedding
  -> Milvus
"""
