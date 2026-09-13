"""用户管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.core.audit import audit_async
from app.models.schemas import AdminUserCreate, AdminUserUpdate
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter()


@router.get("", summary="用户列表")
async def list_users(
    user: dict = Depends(require_permission("users", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    data, total = await UserService.list_users_async(db, page, page_size, keyword, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="创建用户")
async def create_user(
    body: AdminUserCreate,
    request: Request,
    user: dict = Depends(require_permission("users", "create")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await UserService.create_user_async(db, body.username, body.password, body.email, body.phone, body.role)
        AuthService.invalidate_user_permissions(result["id"])
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="users", action="create",
            target_id=str(result["id"]), detail={"username": body.username, "role": body.role},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    request: Request,
    user: dict = Depends(require_permission("users", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await UserService.update_user_async(db, user_id, body.email, body.phone, body.status)
        AuthService.invalidate_user_permissions(user_id)
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="users", action="update",
            target_id=str(user_id), detail=body.model_dump(exclude_none=True),
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}/ban", summary="封禁/解封用户")
async def ban_user(
    user_id: int,
    request: Request,
    user: dict = Depends(require_permission("users", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await UserService.ban_user_async(db, user_id)
        AuthService.invalidate_user_permissions(user_id)
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="users", action="ban",
            target_id=str(user_id), detail={"status": result["status"]},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{user_id}/addresses", summary="用户地址列表")
async def get_addresses(user_id: int, user: dict = Depends(require_permission("users", "read")), db: AsyncSession = Depends(get_db)):
    data = await UserService.get_addresses_async(db, user_id)
    return {"code": 0, "data": data}
