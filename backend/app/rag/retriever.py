"""
Milvus 在线检索模块

文档解析、切块和入库由 scripts/prepare_documents.py、scripts/build_chunks.py、scripts/ingest_knowledge_base.py 负责，
这里只负责连接 Milvus、检查 collection、把用户问题向量化并搜索
存在的原因是：RAG 的在线路径要尽量短，只做“问题向量化 -> Milvus 检索 -> 过滤低分结果”
"""

import logging
import socket
from urllib.parse import urlparse

from langchain_openai import OpenAIEmbeddings
from pymilvus import MilvusClient

from backend.app.core.config import get_settings


# 日志和配置：统一从 .env 读取 Milvus、Embedding 和阈值配置
logger = logging.getLogger(__name__)
settings = get_settings()

MILVUS_URI = settings.milvus_uri
MILVUS_DB_NAME = settings.milvus_db_name
MILVUS_COLLECTION_NAME = settings.milvus_collection_name
REBUILD_COLLECTION = settings.milvus_rebuild_collection
MILVUS_TOKEN = settings.milvus_token

EMBED_MODEL_NAME = settings.siliconflow_embed_model
EMBED_DIM = settings.siliconflow_embed_dim

MIN_RAG_SCORE = settings.min_rag_score
MILVUS_TIMEOUT_SECONDS = settings.milvus_timeout_seconds

# 全局缓存变量：避免每次检索都重复创建 Milvus 客户端和 Embedding 客户端
_client: MilvusClient | None = None
_embedding_model: OpenAIEmbeddings | None = None
_initialized = False


# 检查 Milvus TCP 端点是否可连，提前发现服务没启动或端口不通的问题
def _check_milvus_endpoint():
    parsed = urlparse(MILVUS_URI)
    host = parsed.hostname
    port = parsed.port

    if not host and ":" in MILVUS_URI:
        host, raw_port = MILVUS_URI.rsplit(":", 1)
        port = int(raw_port)

    if not host:
        return

    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    with socket.create_connection(
        (host, port),
        timeout=MILVUS_TIMEOUT_SECONDS,
    ):
        return


# 获取 Milvus 客户端：首次调用时创建数据库并切换到项目使用的 database
def get_client() -> MilvusClient:
    global _client

    if _client is None:
        _check_milvus_endpoint()

        client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
        existing_dbs = client.list_databases(timeout=MILVUS_TIMEOUT_SECONDS)

        if MILVUS_DB_NAME not in existing_dbs:
            client.create_database(
                db_name=MILVUS_DB_NAME,
                timeout=MILVUS_TIMEOUT_SECONDS,
            )

        client.use_database(db_name=MILVUS_DB_NAME)
        _client = client

    return _client


# 获取 Embedding 模型客户端：使用 SiliconFlow 兼容 OpenAI 的接口生成向量
def get_embedding_model() -> OpenAIEmbeddings:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = OpenAIEmbeddings(
            model=EMBED_MODEL_NAME,
            base_url=settings.siliconflow_base_url,
            api_key=settings.siliconflow_api_key,
            tiktoken_enabled=False,
            check_embedding_ctx_length=False,
            timeout=20,
            max_retries=1,
        )

    return _embedding_model


# 创建 Milvus collection：入库脚本会调用它，重建集合以保证数据和 schema 一致
def create_collection(client: MilvusClient):
    if client.has_collection(
        collection_name=MILVUS_COLLECTION_NAME,
        timeout=MILVUS_TIMEOUT_SECONDS,
    ):
        client.drop_collection(
            collection_name=MILVUS_COLLECTION_NAME,
            timeout=MILVUS_TIMEOUT_SECONDS,
        )

    client.create_collection(
        collection_name=MILVUS_COLLECTION_NAME,
        dimension=EMBED_DIM,
        metric_type="COSINE",
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


# 确保 collection 已存在并尝试加载；在线检索只检查，不在请求中重建知识库
def ensure_collection_ready():
    global _initialized

    logger.debug("RAG ensure_collection_ready start")

    if _initialized:
        logger.debug("RAG collection already initialized")
        return

    logger.debug("RAG get milvus client start")
    client = get_client()
    logger.debug("RAG get milvus client done")

    logger.debug("RAG check collection start: %s", MILVUS_COLLECTION_NAME)
    if not client.has_collection(
        collection_name=MILVUS_COLLECTION_NAME,
        timeout=MILVUS_TIMEOUT_SECONDS,
    ):
        raise RuntimeError(
            "Milvus collection does not exist. "
            "Please run: python -m scripts.ingest_knowledge_base"
        )
    logger.debug("RAG check collection done")

    try:
        logger.debug("RAG load collection start")
        client.load_collection(
            collection_name=MILVUS_COLLECTION_NAME,
            timeout=MILVUS_TIMEOUT_SECONDS,
        )
        logger.debug("RAG load collection done")
    except Exception as error:
        logger.warning("RAG load collection skipped or failed: %s", error)

    _initialized = True
    logger.debug("RAG ensure_collection_ready done")


# Milvus 健康检查：给 /health 使用，返回 collection 是否存在以及错误详情
def check_milvus_health() -> dict:
    try:
        client = get_client()
        collection_exists = client.has_collection(
            collection_name=MILVUS_COLLECTION_NAME,
            timeout=MILVUS_TIMEOUT_SECONDS,
        )

        return {
            "ok": collection_exists,
            "uri": MILVUS_URI,
            "database": MILVUS_DB_NAME,
            "collection": MILVUS_COLLECTION_NAME,
            "collection_exists": collection_exists,
        }
    except Exception as error:
        return {
            "ok": False,
            "uri": MILVUS_URI,
            "database": MILVUS_DB_NAME,
            "collection": MILVUS_COLLECTION_NAME,
            "collection_exists": False,
            "error": str(error),
            "error_type": type(error).__name__,
        }


# 对外检索函数：输入用户问题，输出达到相关度阈值的知识库片段列表
def search_documents(query: str, top_k: int = 3) -> list[dict]:
    global _initialized

    logger.debug("RAG search_documents start: %s", query)
    ensure_collection_ready()

    logger.debug("RAG get client/model start")
    client = get_client()
    embedding_model = get_embedding_model()
    logger.debug("RAG get client/model done")

    logger.debug("RAG embedding start")
    query_vector = embedding_model.embed_query(query)
    logger.debug("RAG embedding done")

    logger.debug("RAG milvus search start")
    try:
        hits = client.search(
            collection_name=MILVUS_COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
            timeout=MILVUS_TIMEOUT_SECONDS,
            output_fields=[
                "doc_id",
                "title",
                "source",
                "source_path",
                "doc_type",
                "business_area",
                "risk_level",
                "content",
                "chunk_id",
            ],
        )
    except Exception:
        _initialized = False
        raise
    logger.debug("RAG milvus search done")

    results = []
    for hit in hits[0]:
        entity = hit.get("entity", {})
        score = float(hit.get("distance", 0))
        if score < MIN_RAG_SCORE:
            continue

        # doc
        results.append(
            {
                "doc_id": entity.get("doc_id", ""),
                "title": entity.get("title", ""),
                "source": entity.get("source", ""),
                "source_path": entity.get("source_path", ""),
                "doc_type": entity.get("doc_type", ""),
                "business_area": entity.get("business_area", ""),
                "risk_level": entity.get("risk_level", ""),
                "content": entity.get("content", ""),
                "chunk_id": entity.get("chunk_id", ""),
                "score": score,
            }
        )

    return results
