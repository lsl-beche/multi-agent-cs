"""依赖注入：JWT认证 + 异步数据库会话"""
from collections.abc import AsyncIterator
from typing import Any, Callable

import jwt
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.db import AsyncSessionLocal

# ── 数据库会话 ────────────────────────────────────────

async def get_async_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 异步依赖：请求级 AsyncSession"""
    async with AsyncSessionLocal() as db:
        yield db


async def get_db() -> AsyncIterator[AsyncSession]:
    """兼容别名：路由可继续使用 get_db"""
    async for db in get_async_db():
        yield db


async def run_sync(db: AsyncSession, func: Callable, *args, **kwargs):
    """在 AsyncSession 的绿色线程中执行同步 Service/查询逻辑"""
    return await db.run_sync(lambda session: func(session, *args, **kwargs))


# ── JWT认证依赖 ───────────────────────────────────────

def _extract_token(request: Request) -> str:
    """从 Authorization 头提取 Bearer Token"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌为空",
        )
    return token


def _decode_access_token(token: str) -> dict[str, Any]:
    """解码并验证 JWT access token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误",
        )
    return payload


async def current_user(request: Request) -> dict[str, Any]:
    """FastAPI Depends：获取当前登录用户的JWT payload（完整验证）"""
    token = _extract_token(request)
    return _decode_access_token(token)


async def verify_token(request: Request) -> dict[str, Any]:
    """向后兼容接口：与 current_user 等价，验证完整 JWT"""
    return await current_user(request)
