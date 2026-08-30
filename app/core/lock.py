"""Redis 分布式锁：定时任务/写操作防多实例重复执行"""
import contextlib
import time
import uuid

from app.core.redis_client import get_redis


@contextlib.contextmanager
def redis_lock(name: str, ttl: int = 60, wait_seconds: float = 0.0):
    """SET NX EX 分布式锁；wait_seconds>0 时阻塞等待获取"""
    lock_key = f"csagent:lock:{name}"
    token = uuid.uuid4().hex
    r = get_redis()
    deadline = time.time() + wait_seconds
    while True:
        try:
            acquired = r.set(lock_key, token, nx=True, ex=ttl)
        except Exception:
            acquired = False
        if acquired:
            break
        if time.time() >= deadline:
            raise TimeoutError(f"获取分布式锁超时: {name}")
        time.sleep(0.1)
    try:
        yield
    finally:
        try:
            # 仅释放自己的锁（Lua 保证原子性）
            r.eval("if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                   1, lock_key, token)
        except Exception:
            pass
