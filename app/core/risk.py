"""风控规则引擎 v1：注册/登录/领券/下单/支付 五类场景

设计：evaluate(scene, ctx) → {action, score, reason}
- ctx：{ user_id, ip, device, phone, address, amount, ... }
- 规则优先级：黑名单（block）> 频率/聚合阈值（review→block）> 金额异常（review）> allow
- 每次判定写 risk_events（可复审），指标：csagent_risk_blocked_total
"""
import asyncio
from datetime import datetime

from sqlalchemy import select

from app.config.settings import settings
from app.core.db import SessionLocal
from app.core.metrics import RISK_BLOCKED, RISK_EVENTS
from app.models.tables import RiskBlacklist, RiskEvent


def _log(scene: str, subject: str, subject_value: str, score: int, action: str, detail: dict) -> None:
    db = SessionLocal()
    try:
        db.add(RiskEvent(scene=scene, subject=subject, subject_value=subject_value[:128],
                         score=score, action=action, detail=detail))
        db.commit()
    finally:
        db.close()


def _window_count(key: str, window: int = 60) -> int:
    from app.core.redis_client import get_redis
    r = get_redis()
    n = r.incr(key)
    if n == 1:
        r.expire(key, window)
    return n


def evaluate(scene: str, ctx: dict) -> dict:
    db = SessionLocal()
    try:
        # 0) 黑名单（user/ip/device/phone/address）
        for kind, key in [("user", "user_id"), ("ip", "ip"), ("device", "device"),
                          ("phone", "phone"), ("address", "address")]:
            val = ctx.get(key)
            if not val:
                continue
            hit = db.execute(select(RiskBlacklist).where(
                RiskBlacklist.kind == kind, RiskBlacklist.value == str(val),
                (RiskBlacklist.expires_at.is_(None) | (RiskBlacklist.expires_at > datetime.utcnow())),
            )).scalars().first()
            if hit:
                RISK_BLOCKED.labels(scene=scene).inc()
                RISK_EVENTS.labels(action="block").inc()
                _log(scene, kind, str(val), 100, "block", {"rule": "blacklist", "reason": hit.reason})
                return {"action": "block", "score": 100, "reason": hit.reason}

        # 1) 频率/聚合规则
        ip = ctx.get("ip") or "unknown"
        freq = {
            "register": ("register:ip", 10, 60, 40),
            "login": ("login:fail_ip", 5, 600, 40),
            "coupon": ("coupon:user", 3, 3600, 50),
            "order": ("order:address", 5, 86400, 50),
            "payment": ("pay:user", 10, 3600, 50),
        }
        if scene in freq:
            key_prefix, limit, window, score = freq[scene]
            subject_val = ctx.get("user_id") or ip
            n = _window_count(f"csagent:risk:{key_prefix}:{subject_val}", window)
            if n > limit:
                action = "block" if n > limit * 2 else "review"
                if action == "block":
                    RISK_BLOCKED.labels(scene=scene).inc()
                RISK_EVENTS.labels(action=action).inc()
                _log(scene, "subject", str(subject_val), score, action,
                     {"rule": "frequency", "count": n, "limit": limit})
                return {"action": action, "score": score, "reason": f"{scene} 频率异常（{n}/{limit}）"}

        # 2) 金额异常（支付/下单）
        amount = ctx.get("amount", 0)
        if scene in ("payment", "order") and amount and float(amount) > getattr(settings, "risk_max_amount", 50000):
            RISK_EVENTS.labels(action="review").inc()
            _log(scene, "user", str(ctx.get("user_id", "")), 60, "review", {"rule": "amount", "amount": amount})
            return {"action": "review", "score": 60, "reason": "金额异常，需人工复核"}

        RISK_EVENTS.labels(action="allow").inc()
        _log(scene, "subject", str(ctx.get("user_id") or ip), 0, "allow", {})
        return {"action": "allow", "score": 0, "reason": "通过"}
    finally:
        db.close()


async def evaluate_async(scene: str, ctx: dict) -> dict:
    """异步入口：同步风控逻辑放入线程池，避免阻塞事件循环。"""
    return await asyncio.to_thread(evaluate, scene, ctx)
