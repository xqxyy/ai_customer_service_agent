"""
项目配置中心

这个文件集中读取 .env 和系统环境变量，统一管理模型、Embedding、Milvus、
RAG 阈值、数据库连接等配置。它存在的原因是：工程化项目不能把 API 地址、
端口、数据库 URL 写死在业务代码里，否则迁移环境和部署时很难维护
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# 配置类：Pydantic 会自动从 .env 或系统环境变量中读取同名配置
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_root: Path = Path(__file__).resolve().parents[3]

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"

    siliconflow_api_key: str
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_embed_model: str = "BAAI/bge-m3"
    siliconflow_embed_dim: int = 1024

    milvus_uri: str = "http://localhost:19530"
    milvus_db_name: str = "customer_service_rag"
    milvus_collection_name: str = "customer_service_docs"
    milvus_rebuild_collection: bool = False
    milvus_token: str | None = None
    milvus_timeout_seconds: float = 5.0

    customer_service_db_path: str = "customer_service.db"
    min_rag_score: float = 0.7

    database_url: str = "sqlite:///./customer_service.db"
    database_connect_timeout_seconds: int = 5

    # SQLite 路径兼容属性：旧版本如果使用 SQLite 文件，会把相对路径解析到项目根目录下
    @property
    def sqlite_path(self) -> Path:
        path = Path(self.customer_service_db_path)
        if path.is_absolute():
            return path
        return self.project_root / path


# 获取全局配置对象：使用缓存避免每次导入模块时重复解析 .env
@lru_cache
def get_settings() -> Settings:
    return Settings()
