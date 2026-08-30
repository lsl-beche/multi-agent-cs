"""向量化封装：BGE 中文 Embedding 模型（单例 + 查询向量缓存）

职责：
1. get_embeddings()：进程级单例嵌入模型
   - 配置支持 bge-small（轻量，CPU 推理快 3-5 倍；.env 当前为 bge-large 本地路径）
   - normalize_embeddings=True：输出归一化向量，余弦相似度=点积
   - query_instruction：BGE 检索指令（中文场景必需，否则效果打折）
2. embed_query_cached()：带进程内 TTL 缓存的查询向量
   - 关键优化：同一请求中"意图识别 / 知识检索 / QA 缓存匹配"
     三处都嵌入同一问题，缓存后只算一次（实测每次省 0.5-1.5s）
   - TTL 10 分钟，容量 512（满则清空，简单淘汰）

性能影响：CPU 上 bge-large 单次嵌入约 0.3-1.5s，
缓存命中可把重复嵌入的开销降到 ~0ms。
"""
import hashlib
import threading
import time

import numpy as np
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

from app.config.settings import settings

_embeddings: HuggingFaceBgeEmbeddings | None = None

# 进程内查询向量缓存：同一请求中 意图识别/知识检索/QA缓存 复用同一次嵌入结果
_embed_cache: dict[str, tuple[float, np.ndarray]] = {}
_embed_cache_lock = threading.Lock()
_EMBED_CACHE_TTL = 600   # 10分钟
_EMBED_CACHE_MAX = 512   # 上限，防止内存无限增长


def get_embeddings() -> HuggingFaceBgeEmbeddings:
    """单例获取Embedding模型（首次加载较慢，建议启动时预热）"""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceBgeEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},  # TODO: 有GPU时改为 cuda
            encode_kwargs={"normalize_embeddings": True},  # 归一化，适配余弦相似度
            query_instruction="为这个句子生成表示以用于检索相关文章：",  # BGE检索指令
        )
    return _embeddings


def embed_query_cached(text: str) -> np.ndarray:
    """带进程内 TTL 缓存的 query 嵌入

    返回：归一化 float32 向量（norm=0 时原样返回）
    并发：threading.Lock 保护缓存读写（FastAPI 线程池场景安全）
    """
    key = hashlib.sha1((text or "").encode("utf-8")).hexdigest()
    now = time.time()
    with _embed_cache_lock:
        hit = _embed_cache.get(key)
        if hit is not None and now - hit[0] < _EMBED_CACHE_TTL:
            return hit[1]
    vec = np.asarray(get_embeddings().embed_query(text or ""), dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    with _embed_cache_lock:
        if len(_embed_cache) >= _EMBED_CACHE_MAX:
            _embed_cache.clear()  # 简单淘汰：满时清空（TTL短，影响有限）
        _embed_cache[key] = (now, vec)
    return vec
