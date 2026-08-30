"""对话向量记忆（长期记忆之四）：历史问答向量化，跨会话语义召回

用途：用户换一个会话问"上次聊过的普洱熟茶还有别的吗"时，
按语义召回该用户此前相关的问答片段，注入【历史对话记忆】上下文，
实现跨会话"记得你问过什么"。

存储：独立 Chroma 集合 cs_memory（与知识库 cs_knowledge 隔离），
metadata 含 user_id/session_id/ts/ttl_ts（按 TTL 治理，默认 90 天）。

隐私合规：
- user_memory_enabled=False 时不再写入
- delete_user_memory(user_id)：遗忘权接口调用
- cleanup_expired()：清理超龄条目（脚本/定时任务）

检索：similarity_search_by_vector + filter={"user_id": ...}，
只召回该用户自己的历史（不跨用户泄露）。
"""
import logging
import time

from app.config.settings import settings
from app.knowledge.embedding import embed_query_cached, get_embeddings

logger = logging.getLogger(__name__)

_COLLECTION = "cs_memory"
_vectorstore = None


def get_memory_vectorstore():
    """单例获取记忆向量库（独立集合，与知识库分离）"""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore
    from langchain_community.vectorstores import Chroma

    _vectorstore = Chroma(
        collection_name=_COLLECTION,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embeddings(),
    )
    return _vectorstore


def remember(user_id: str, session_id: str, question: str, answer: str) -> bool:
    """记录一轮问答到向量记忆（失败不阻断主流程）"""
    if not settings.user_memory_enabled or not question or not answer:
        return False
    try:
        vs = get_memory_vectorstore()
        text = f"用户：{question[:200]}\n客服：{answer[:300]}"
        vs.add_texts(
            [text],
            metadatas=[{
                "user_id": user_id,
                "session_id": session_id,
                "ts": int(time.time()),
                "type": "dialogue",
                "ttl_ts": int(time.time()) + getattr(settings, "memory_ttl_days", 90) * 86400,
            }],
        )
        return True
    except Exception:
        logger.exception("vector memory remember failed")
        return False


def recall(user_id: str, query: str, top_k: int = 2) -> list[str]:
    """按用户召回与当前问题语义相关的历史问答片段"""
    if not user_id or not query:
        return []
    try:
        vs = get_memory_vectorstore()
        q_vec = embed_query_cached(query)
        docs = vs.similarity_search_by_vector(
            q_vec.tolist(), k=top_k, filter={"user_id": user_id}
        )
        return [d.page_content for d in docs]
    except Exception:
        return []


def delete_user_memory(user_id) -> int:
    """删除指定用户全部向量记忆（遗忘权）"""
    try:
        vs = get_memory_vectorstore()
        vs._collection.delete(where={"user_id": str(user_id)})
        return 1
    except Exception:
        logger.exception("delete vector memory failed: user=%s", user_id)
        return 0


def cleanup_expired(now_ts: int | None = None) -> int:
    """清理超过 TTL 的向量记忆（脚本/定时任务）"""
    now_ts = now_ts or int(time.time())
    try:
        col = get_memory_vectorstore()._collection
        data = col.get(include=["metadatas"])
        metas = data.get("metadatas") or []
        stale_sids = [m["session_id"] for m in metas if (m or {}).get("ttl_ts", 0) < now_ts]
        for sid in stale_sids:
            try:
                col.delete(where={"session_id": sid})
            except Exception:
                pass
        return len(stale_sids)
    except Exception:
        logger.exception("cleanup vector memory failed")
        return 0
