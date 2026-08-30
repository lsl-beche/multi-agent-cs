"""Outbox 事件服务：事务内写入事件，后台 worker 异步投递"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.events import publish
from app.repositories import OutboxRepository


async def record_outbox(
    db: AsyncSession,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """在业务事务内记录 outbox 事件"""
    repo = OutboxRepository(db)
    await repo.add_event(aggregate_type, aggregate_id, event_type, payload)


async def dispatch_pending(limit: int = 100) -> int:
    """轮询并投递 pending 事件，返回处理数量"""
    dispatched = 0
    async with AsyncSessionLocal() as db:
        repo = OutboxRepository(db)
        events = await repo.pending(limit)
        for event in events:
            try:
                await publish(event.event_type, event.payload)
                await repo.mark_published(event.id)
                dispatched += 1
            except Exception as exc:  # noqa: BLE001
                await repo.mark_failed(event.id, str(exc))
        await db.commit()
    return dispatched


async def run_outbox_worker(interval_seconds: int = 2, stop_event: asyncio.Event | None = None) -> None:
    """后台循环 worker"""
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            await dispatch_pending()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(interval_seconds)
