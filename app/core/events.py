"""领域事件总线：进程内异步发布/订阅（Kafka 适配器预留）

事件流：order.created → payment.paid → shipment.track_refreshed → refund.completed ...
生产环境可将 EVENT_BUS_BACKEND 切换为 kafka，由 KafkaEventPublisher 转发到消息队列，
消费者迁移到独立服务；当前内存实现保证单体阶段即可观测与解耦。
"""
import asyncio
import inspect
import logging
import threading
from collections import defaultdict
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict], Awaitable[None]]
_subscribers: dict[str, list[Handler]] = defaultdict(list)


def on(event_name: str):
    """订阅装饰器：@on("order.created")"""
    def decorator(fn: Handler) -> Handler:
        _subscribers[event_name].append(fn)
        return fn
    return decorator


async def publish(event_name: str, payload: dict) -> None:
    """发布事件：并发调用所有订阅者，单个失败不影响其余"""
    handlers = list(_subscribers.get(event_name, []))
    if not handlers:
        return
    results = await asyncio.gather(
        *(asyncio.create_task(_safe_call(h, event_name, payload)) for h in handlers),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            logger.exception("event handler failed: %s", event_name)


def publish_sync(event_name: str, payload: dict) -> None:
    """同步上下文发布事件（供后台线程/同步服务调用）"""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(publish(event_name, payload), loop)
            return
    except RuntimeError:
        pass
    # 无事件循环：直接同步执行处理器（指标/日志场景足够）
    for handler in list(_subscribers.get(event_name, [])):
        try:
            result = handler(event_name, payload)
            if inspect.isawaitable(result):
                threading.Thread(target=lambda c: asyncio.run(c), args=(result,), daemon=True).start()
        except Exception:
            logger.exception("sync event handler error: %s", event_name)


async def _safe_call(handler: Handler, event_name: str, payload: dict) -> None:
    try:
        result = handler(event_name, payload)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception("event handler error: %s", event_name)


def register_builtin_consumers() -> None:
    """注册内置消费者（指标/日志），幂等"""
    from app.events import consumers  # noqa: F401
