"""限流中间件：Redis 滑动窗口（分布式）+ 内存降级（单实例）"""
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.settings import settings

# 路由分级限流配置（每分钟）
RATE_LIMITS = {
    "/api/auth/login": settings.rate_limit_login,
    "/api/auth/register": settings.rate_limit_login,
    "/api/orders": settings.rate_limit_order,
}

# Lua 脚本：原子化滑动窗口计数
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- 移除窗口外的旧记录
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- 当前窗口内的请求数
local count = redis.call('ZCARD', key)

if count >= limit then
    return 0
end

-- 添加当前请求
redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
redis.call('EXPIRE', key, window)
return 1
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 分布式滑动窗口限流，单实例时降级为内存限流"""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)  # 内存降级
        self._redis = None
        self._lua_sha = None

    def _get_redis(self):
        if self._redis is None:
            try:
                from app.core.redis_client import get_redis
                self._redis = get_redis()
                if self._redis:
                    self._lua_sha = self._redis.script_load(SLIDING_WINDOW_LUA)
            except Exception:
                self._redis = None
        return self._redis

    def _get_rate_limit(self, path: str) -> int:
        """根据路径匹配限流规则"""
        for prefix, limit in RATE_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return settings.rate_limit_default

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # 健康检查不限流
        if path.startswith("/api/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limit = self._get_rate_limit(path)
        window = 60  # 1分钟窗口

        # 尝试 Redis 分布式限流
        r = self._get_redis()
        if r and self._lua_sha:
            try:
                key = f"rate_limit:{client_ip}:{path.split('/')[2] if len(path.split('/')) > 2 else 'global'}"
                now_ms = int(time.time() * 1000)
                allowed = r.evalsha(self._lua_sha, 1, key, now_ms, window * 1000, limit)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "请求过于频繁，请稍后再试"},
                        headers={"Retry-After": str(window)},
                    )
                return await call_next(request)
            except Exception:
                pass  # Redis 不可用时降级

        # 降级：内存滑动窗口（单实例有效）
        now = time.monotonic()
        window_list = [t for t in self._hits[client_ip] if now - t < window]
        if len(window_list) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": str(window)},
            )
        window_list.append(now)
        self._hits[client_ip] = window_list
        return await call_next(request)
