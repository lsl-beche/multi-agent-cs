"""用户管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, run_sync
from app.api.middleware.auth import require_permission
from app.models.schemas import AdminUserCreate, AdminUserUpdate
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
    data, total = await run_sync(db, UserService.list_users, page, page_size, keyword, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="创建用户")
async def create_user(body: AdminUserCreate, user: dict = Depends(require_permission("users", "create")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, UserService.create_user, body.username, body.password, body.email, body.phone, body.role)
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}", summary="更新用户")
async def update_user(user_id: int, body: AdminUserUpdate, user: dict = Depends(require_permission("users", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, UserService.update_user, user_id, body.email, body.phone, body.status)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}/ban", summary="封禁/解封用户")
async def ban_user(user_id: int, user: dict = Depends(require_permission("users", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, UserService.ban_user, user_id)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{user_id}/addresses", summary="用户地址列表")
async def get_addresses(user_id: int, user: dict = Depends(require_permission("users", "read")), db: AsyncSession = Depends(get_db)):
    data = await run_sync(db, UserService.get_addresses, user_id)
    return {"code": 0, "data": data}
