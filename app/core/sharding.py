"""数据分片基础设施：按 user_id 哈希路由到 PostgreSQL shard

设计：
- 分片数由 PG_SHARD_URLS 长度决定（开发=1，行为与单库一致）；
- 路由键统一用 user_id（订单/支付/会话均按用户归属），避免跨分片事务；
- 迁移到分片时，先双写/校验，再切换读，最后切写（见 docs/scaling-playbook.md）。
"""
import hashlib
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def shard_count() -> int:
    return max(1, len(settings.pg_shard_urls))


def shard_index(user_id: int | str) -> int:
    """一致性哈希路由：按 user_id 字符串哈希取模，保证同一用户永远落同一分片"""
    n = shard_count()
    if n == 1:
        return 0
    key = str(user_id).encode()
    return int(hashlib.md5(key).hexdigest(), 16) % n


@lru_cache(maxsize=64)
def _shard_engine(index: int):
    urls = settings.pg_shard_urls
    url = urls[index] if urls else settings.postgres_url
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600, pool_size=10, max_overflow=5)


def get_shard_sessionmaker(index: int):
    return sessionmaker(bind=_shard_engine(index), autoflush=False, autocommit=False)


def get_db_for_user(user_id: int | str):
    """获取用户所在分片的 Session 工厂（开发环境=默认单库）"""
    if shard_count() == 1:
        from app.core.db import SessionLocal
        return SessionLocal
    return get_shard_sessionmaker(shard_index(user_id))
