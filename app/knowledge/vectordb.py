"""向量数据库封装（步骤三）：Chroma（开发）/ Milvus（生产）统一接口

- 开发/当前：Chroma（本地持久化，data/vectordb/）
- 生产：Milvus（TODO 已预留，需引入 pymilvus 依赖）

单例设计：get_vectorstore() 进程内只创建一次（Chroma 初始化约 800ms，
重复创建是此前知识检索慢（900ms+）的主因之一，已修复）。

集合约定：
cs_knowledge —— 知识库 FAQ（metadata: category/question/version）
cs_memory    —— 对话向量记忆（vector_memory.py 独立维护，不在此模块）
"""
from langchain_core.vectorstores import VectorStore

from app.config.settings import settings
from app.knowledge.embedding import get_embeddings

COLLECTION_NAME = "cs_knowledge"

_vectorstore: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    """单例获取向量库实例（进程级缓存，避免重复初始化 Chroma）"""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore
    if settings.vector_db_type == "chroma":
        from langchain_community.vectorstores import Chroma

        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=settings.chroma_persist_dir,
            embedding_function=get_embeddings(),
        )
        return _vectorstore
    if settings.vector_db_type == "milvus":
        # TODO: 生产环境启用
        # from langchain_community.vectorstores import Milvus
        # return Milvus(
        #     embedding_function=get_embeddings(),
        #     collection_name=COLLECTION_NAME,
        #     connection_args={"host": settings.milvus_host, "port": settings.milvus_port},
        # )
        raise NotImplementedError("Milvus 接入待实现，请先将 VECTOR_DB_TYPE 设为 chroma")
    raise ValueError(f"不支持的向量库类型: {settings.vector_db_type}")
