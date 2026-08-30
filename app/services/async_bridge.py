"""同步 Service 到 AsyncSession 的过渡适配器。

该桥接将同步方法包装为 async 方法，在 AsyncSession 的绿色线程中执行；
后续可逐方法替换为真正原生异步实现。
"""
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession


def async_adapter(func: Callable) -> Callable[..., Any]:
    async def wrapper(db: AsyncSession, *args, **kwargs):
        return await db.run_sync(lambda session: func(session, *args, **kwargs))

    return wrapper
