"""LLM 用户配额：按用户/窗口计数，防止成本失控与刷接口。

存储：Redis `csagent:quota:llm:<user_id>`，TTL=配置窗口。
降级：Redis 不可用时放行（业务可用性优先；配额属于成本保护，非安全兜底）。
"""
from app.config.settings import settings
from app.core.metrics import QUOTA_BLOCKED

_PREFIX = "csagent:quota:llm:"


def _ttl() -> int:
    return max(60, int(settings.llm_quota_window_hours) * 3600)


def used(user_id: str) -> int:
    try:
        from app.core.redis_client import get_redis
        return int(get_redis().get(_PREFIX + str(user_id)) or 0)
    except Exception:
        return 0


def allowed(user_id: str) -> tuple[bool, int, int]:
    if not user_id:
        return True, 0, settings.llm_daily_quota
    u = used(user_id)
    return u < settings.llm_daily_quota, u, settings.llm_daily_quota


def consume(user_id: str) -> bool:
    """消耗一次 AI 配额；超出返回 False。"""
    if not user_id:
        return True
    try:
        from app.core.redis_client import get_redis
        r = get_redis()
        key = _PREFIX + str(user_id)
        n = r.incr(key)
        if n == 1:
            r.expire(key, _ttl())
        if n > settings.llm_daily_quota:
            QUOTA_BLOCKED.inc()
            return False
        return True
    except Exception:
        return True


async def allowed_async(user_id: str) -> tuple[bool, int, int]:
    import asyncio
    return await asyncio.to_thread(allowed, user_id)


async def consume_async(user_id: str) -> bool:
    import asyncio
    return await asyncio.to_thread(consume, user_id)
