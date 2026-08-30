"""依赖注入：JWT认证 + 数据库会话"""
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.db import SessionLocal


# ── 数据库会话 ────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
