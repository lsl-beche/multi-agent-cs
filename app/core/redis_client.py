"""Redis客户端：会话缓存 + 高频问答缓存（成本优化，减少LLM调用次数）"""
import hashlib
import time

import numpy as np
import redis

from app.config.settings import settings
from app.knowledge.embedding import embed_query_cached

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        if settings.redis_cluster_nodes:
            # Redis Cluster（生产）：主从自动分片
            from redis.cluster import RedisCluster
            _client = RedisCluster(
                startup_nodes=[redis.cluster.ClusterNode(**n) for n in settings.redis_cluster_nodes],
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
                retry_on_timeout=False,
            )
        else:
            _client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,  # 连接超时1秒，快速失败
                socket_timeout=1,           # 读写超时1秒
                retry_on_timeout=False,     # 不重试，避免级联延迟
                health_check_interval=30,   # 每30s检测连接存活
            )
    return _client


# ===== 高频问答缓存（对应7.2 成本优化）=====
_QA_PREFIX = "csagent:qa:"
_QA_EMB_PREFIX = "csagent:qa:emb:"
_QA_INDEX_KEY = "csagent:qa:index"       # ZSET：question -> 时间戳，用于语义匹配索引
_QA_TTL = 60 * 60 * 24                  # 1天
_QA_INDEX_MAX = 500                     # 索引容量上限，超限删除最旧

_QA_SIM_THRESHOLD = settings.qa_sim_threshold  # 阈值可配置（0.88~0.93 灰度调优）


def _qkey(q: str) -> str:
    return _QA_PREFIX + q


def _embkey(q: str) -> str:
    return _QA_EMB_PREFIX + hashlib.sha1(q.encode("utf-8")).hexdigest()[:16]


def _embed(q: str) -> np.ndarray:
    """当前问题向量（归一化，缓存查询每轮只需计算一次）"""
    return embed_query_cached(q)


def get_cached_answer(question: str) -> str | None:
    """查询缓存：先精确匹配，再语义相似匹配。任何异常均静默降级为未命中。"""
    q = (question or "").strip()
    if not q:
        return None
    try:
        r = get_redis()
        # 1) 精确命中
        exact = r.get(_qkey(q))
        if exact is not None:
            from app.core.metrics import QA_CACHE_HITS
            QA_CACHE_HITS.inc()
            return exact

        # 2) 语义命中：与已缓存问题做余弦相似度匹配
        cached_qs = r.zrange(_QA_INDEX_KEY, 0, -1)
        if not cached_qs:
            from app.core.metrics import QA_CACHE_MISSES
            QA_CACHE_MISSES.inc()
            return None
        cached_qs = [x.decode() if isinstance(x, bytes) else x for x in cached_qs]
        q_vec = _embed(q)
        pipe = r.pipeline()
        for cq in cached_qs:
            pipe.get(_embkey(cq))
        embs = pipe.execute()

        best_q, best_sim = None, 0.0
        for cq, raw in zip(cached_qs, embs):
            if not raw:
                continue
            c_vec = np.frombuffer(raw, dtype=np.float32)
            sim = float(np.dot(q_vec, c_vec))
            if sim > best_sim:
                best_q, best_sim = cq, sim
        if best_q is not None and best_sim >= _QA_SIM_THRESHOLD:
            from app.core.metrics import QA_CACHE_HITS
            QA_CACHE_HITS.inc()
            return r.get(_qkey(best_q))
        from app.core.metrics import QA_CACHE_MISSES
        QA_CACHE_MISSES.inc()
    except (redis.RedisError, Exception):
        return None  # 缓存/embedding 不可用时静默降级
    return None


def cache_answer(question: str, answer: str, ttl: int = _QA_TTL) -> None:
    """写入问答缓存：答案 + 问题向量（供语义匹配） + 索引。失败不阻断主流程。"""
    q = (question or "").strip()
    if not q or not answer or len(answer) < 5:
        return
    try:
        r = get_redis()
        if r.exists(_qkey(q)):
            return
        pipe = r.pipeline()
        pipe.setex(_qkey(q), ttl, answer)
        pipe.setex(_embkey(q), ttl, _embed(q).astype(np.float32).tobytes())
        pipe.zadd(_QA_INDEX_KEY, {q: time.time()})
        pipe.execute()

        # 索引超限时删除最旧的问题
        size = r.zcard(_QA_INDEX_KEY)
        if size > _QA_INDEX_MAX:
            stale = r.zrange(_QA_INDEX_KEY, 0, size - _QA_INDEX_MAX - 1)
            for old in stale:
                old_q = old.decode() if isinstance(old, bytes) else old
                r.delete(_qkey(old_q), _embkey(old_q))
            r.zrem(_QA_INDEX_KEY, *stale)
    except (redis.RedisError, Exception):
        pass  # 缓存失败不阻断主流程
