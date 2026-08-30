"""幂等键服务：防止支付、退款、下单重复处理"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import IdempotencyRepository


async def begin_idempotent(
    db: AsyncSession,
    key: str,
    scope: str,
    user_id: str,
    payload: dict | None = None,
    ttl_seconds: int = 3600,
) -> dict | None:
    """返回已有幂等结果；若不存在则写入新键并返回 None"""
    repo = IdempotencyRepository(db)
    existing = await repo.get(key)
    if existing:
        if existing.expires_at <= datetime.now(timezone.utc):
            await db.delete(existing)
            await db.flush()
        else:
            return existing.payload
    try:
        await repo.create(
            key=key,
            scope=scope,
            user_id=str(user_id),
            payload=payload or {},
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
    except IntegrityError:
        await db.rollback()
        existing = await repo.get(key)
        return existing.payload if existing else None
    return None


async def complete_idempotent(db: AsyncSession, key: str, payload: dict) -> None:
    """幂等操作成功后保存结果，后续重复请求直接返回该结果"""
    repo = IdempotencyRepository(db)
    existing = await repo.get(key)
    if existing:
        existing.payload = payload
        await db.commit()
