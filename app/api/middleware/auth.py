"""认证鉴权：JWT验证 + RBAC权限校验（FastAPI依赖工厂模式）"""
from typing import Any, Callable

import jwt
from fastapi import HTTPException, Request, status

from app.config.settings import settings


def get_current_user(request: Request) -> dict:
    """从请求头提取并验证JWT，返回payload"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌类型错误")
        # 实时权限快照：Redis 缓存命中则零额外查询，未命中/角色变更后回源 DB。
        try:
            from app.core.db import SessionLocal
            from app.services.auth_service import AuthService
            db = SessionLocal()
            try:
                snapshot = AuthService.get_permission_snapshot(db, int(payload["sub"]))
            finally:
                db.close()
            payload.update(snapshot)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="权限校验服务不可用，请稍后再试",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_permission(resource: str, action: str) -> Callable:
    """RBAC权限依赖工厂（fail-closed）

    用法（FastAPI Depends）：
        @router.get("/products")
        async def list_products(user: dict = Depends(require_permission("products", "read"))): ...

    行为：
    - 无身份/令牌无效 → 401
    - 权限不足 → 403
    - super_admin → 直接放行
    """
    async def permission_checker(request: Request) -> dict[str, Any]:
        # fail-closed: 无法获取身份一律拒绝
        payload = get_current_user(request)

        # super_admin 拥有全部权限
        if payload.get("role") == "super_admin":
            return payload

        permissions: list[str] = payload.get("permissions", [])
        required = f"{resource}:{action}"
        if required not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {required}",
            )
        return payload

    return permission_checker
