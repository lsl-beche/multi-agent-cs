"""登录防爆破：Redis计数 + 账户锁定"""
import time

from loguru import logger

from app.config.settings import settings

MAX_ATTEMPTS = 5
LOCK_DURATION = 900  # 15分钟


def _get_redis():
    from app.core.redis_client import get_redis
    return get_redis()


def check_login_allowed(username: str, client_ip: str) -> tuple[bool, str]:
    """检查是否允许登录尝试。返回 (是否允许, 原因)"""
    try:
        r = _get_redis()
        if r is None:
            return True, ""

        # 账户维度锁定
        account_key = f"login_guard:account:{username}"
        if r.exists(account_key):
            ttl = r.ttl(account_key)
            return False, f"账户已锁定，请 {ttl // 60 + 1} 分钟后再试"

        # IP维度锁定
        ip_key = f"login_guard:ip:{client_ip}"
        ip_count = r.get(ip_key)
        if ip_count and int(ip_count) >= MAX_ATTEMPTS * 3:
            ttl = r.ttl(ip_key)
            return False, f"该IP登录尝试过于频繁，请 {ttl // 60 + 1} 分钟后再试"
    except Exception:
        logger.warning("登录防爆破 Redis 不可用，暂时放行")

    return True, ""


def record_login_failure(username: str, client_ip: str) -> None:
    """记录登录失败，达到阈值时锁定"""
    try:
        r = _get_redis()
        if r is None:
            return

        account_key = f"login_guard:account:{username}"
        ip_key = f"login_guard:ip:{client_ip}"

        # 账户维度计数
        count = r.incr(account_key)
        r.expire(account_key, LOCK_DURATION)
        if count >= MAX_ATTEMPTS:
            logger.warning(f"账户 {username} 连续 {count} 次登录失败，锁定 {LOCK_DURATION // 60} 分钟")
            r.set(account_key, str(count), ex=LOCK_DURATION)

        # IP维度计数（更宽松，3倍阈值）
        ip_count = r.incr(ip_key)
        r.expire(ip_key, LOCK_DURATION)
    except Exception:
        logger.warning("登录失败计数写入 Redis 失败")


def reset_login_attempts(username: str) -> None:
    """登录成功后重置计数"""
    try:
        r = _get_redis()
        if r is None:
            return
        r.delete(f"login_guard:account:{username}")
    except Exception:
        logger.warning("登录计数重置 Redis 失败")
