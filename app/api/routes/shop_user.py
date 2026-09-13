"""C 端用户路由：地址管理与个人中心（仅 HTTP 适配）"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.api.deps import current_user, get_db
from app.core.audit import audit_async
from app.models.schemas import (
    AddressCreateRequest,
    AddressUpdateRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
)
from app.models.tables import User
from app.services.user_service import UserService

router = APIRouter()


async def get_user_id(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


@router.get("/addresses", summary="地址列表")
async def list_addresses(request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    return {"code": 0, "data": await UserService.get_addresses_async(db, user_id)}


@router.post("/addresses", summary="新增地址")
async def create_address(body: AddressCreateRequest, request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    result = await UserService.create_address_async(db, user_id, body.model_dump())
    return {"code": 0, "data": result, "message": "添加成功"}


@router.put("/addresses/{addr_id}", summary="更新地址")
async def update_address(addr_id: int, body: AddressUpdateRequest, request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    try:
        result = await UserService.update_address_async(db, user_id, addr_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 0, "data": result, "message": "更新成功"}


@router.delete("/addresses/{addr_id}", summary="删除地址")
async def delete_address(addr_id: int, request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    try:
        await UserService.delete_address_async(db, user_id, addr_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 0, "message": "已删除"}


@router.put("/profile", summary="更新个人信息")
async def update_profile(body: ProfileUpdateRequest, request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    await UserService.update_profile_async(db, user_id, body.model_dump(exclude_none=True))
    return {"code": 0, "message": "更新成功"}


@router.put("/password", summary="修改密码")
async def change_password(body: PasswordChangeRequest, request: Request, db=Depends(get_db)):
    user_id = await get_user_id(request)
    try:
        await UserService.change_password_async(
            db, user_id, body.old_password, body.new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "密码修改成功"}


@router.delete("/memory", summary="清除我的客服记忆（遗忘权）")
async def erase_memory(request: Request):
    user_id = await get_user_id(request)
    from app.services.privacy_service import erase_user_data

    result = await asyncio.to_thread(erase_user_data, user_id)
    from app.api.deps import current_user
    payload = await current_user(request)
    await audit_async(
        user_id=user_id, username=payload.get("username", ""), module="privacy", action="memory.erase",
        target_id=str(user_id), detail=result,
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "data": result, "message": "客服记忆已清除"}


@router.delete("", summary="注销账号（软注销 + 记忆清除）")
async def delete_account(request: Request, db=Depends(get_db)):
    """个保法注销权：账号软注销（status=banned），并联动清除客服记忆"""
    user_id = await get_user_id(request)
    from app.services.privacy_service import erase_user_data
    await asyncio.to_thread(erase_user_data, user_id)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        user.status = "banned"
        await db.commit()
        from app.api.deps import current_user
        payload = await current_user(request)
        await audit_async(
            user_id=user_id, username=payload.get("username", ""), module="privacy", action="account.delete",
            target_id=str(user_id), detail={"status": user.status},
            ip_address=request.client.host if request.client else None,
        )
    return {"code": 0, "message": "账号已注销，客服记忆已清除"}
