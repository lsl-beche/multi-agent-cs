"""用户管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
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
    db: Session = Depends(get_db),
):
    data, total = UserService.list_users(db, page, page_size, keyword, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="创建用户")
async def create_user(body: AdminUserCreate, user: dict = Depends(require_permission("users", "create")), db: Session = Depends(get_db)):
    try:
        result = UserService.create_user(db, body.username, body.password, body.email, body.phone, body.role)
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}", summary="更新用户")
async def update_user(user_id: int, body: AdminUserUpdate, user: dict = Depends(require_permission("users", "update")), db: Session = Depends(get_db)):
    try:
        result = UserService.update_user(db, user_id, body.email, body.phone, body.status)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{user_id}/ban", summary="封禁/解封用户")
async def ban_user(user_id: int, user: dict = Depends(require_permission("users", "update")), db: Session = Depends(get_db)):
    try:
        result = UserService.ban_user(db, user_id)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{user_id}/addresses", summary="用户地址列表")
async def get_addresses(user_id: int, user: dict = Depends(require_permission("users", "read")), db: Session = Depends(get_db)):
    data = UserService.get_addresses(db, user_id)
    return {"code": 0, "data": data}
