"""C 端用户路由：地址管理 + 个人中心"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.core.security import hash_password, verify_password
from app.models.tables import Address, User

router = APIRouter()


# ── 辅助 ──

async def get_user_id(request: Request, db: AsyncSession) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


def _addr_to_dict(a: Address) -> dict:
    return {
        "id": a.id,
        "receiver_name": a.receiver,
        "receiver_phone": a.phone,
        "province": a.province,
        "city": a.city,
        "district": a.district,
        "detail": a.detail,
        "is_default": a.is_default,
    }


# ── 地址管理 ──

@router.get("/addresses", summary="地址列表")
async def list_addresses(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    addrs = (await db.execute(
        select(Address).where(Address.user_id == user_id).order_by(Address.is_default.desc(), Address.id.desc())
    )).scalars().all()
    return {"code": 0, "data": [_addr_to_dict(a) for a in addrs]}


@router.post("/addresses", summary="新增地址")
async def create_address(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    body = await request.json()
    if body.get("is_default"):
        await db.execute(update(Address).where(Address.user_id == user_id).values(is_default=False))
    addr = Address(
        user_id=user_id,
        receiver=body.get("receiver_name", ""),
        phone=body.get("receiver_phone", ""),
        province=body.get("province", ""),
        city=body.get("city", ""),
        district=body.get("district", ""),
        detail=body.get("detail", ""),
        is_default=bool(body.get("is_default")),
    )
    db.add(addr)
    await db.commit()
    await db.refresh(addr)
    return {"code": 0, "data": _addr_to_dict(addr), "message": "添加成功"}


@router.put("/addresses/{addr_id}", summary="更新地址")
async def update_address(addr_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    addr = (await db.execute(select(Address).where(Address.id == addr_id, Address.user_id == user_id))).scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")
    body = await request.json()
    if body.get("is_default"):
        await db.execute(update(Address).where(Address.user_id == user_id).values(is_default=False))
    addr.receiver = body.get("receiver_name", addr.receiver)
    addr.phone = body.get("receiver_phone", addr.phone)
    addr.province = body.get("province", addr.province)
    addr.city = body.get("city", addr.city)
    addr.district = body.get("district", addr.district)
    addr.detail = body.get("detail", addr.detail)
    addr.is_default = bool(body.get("is_default", addr.is_default))
    await db.commit()
    return {"code": 0, "data": _addr_to_dict(addr), "message": "更新成功"}


@router.delete("/addresses/{addr_id}", summary="删除地址")
async def delete_address(addr_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    addr = (await db.execute(select(Address).where(Address.id == addr_id, Address.user_id == user_id))).scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")
    db.delete(addr)
    await db.commit()
    return {"code": 0, "message": "已删除"}


# ── 个人中心 ──

@router.put("/profile", summary="更新个人信息")
async def update_profile(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    body = await request.json()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 昵称存到 username 的变体逻辑：User 表没有 nickname 字段，这里用 phone 暂存
    if "phone" in body:
        user.phone = body["phone"]
    if "email" in body:
        user.email = body["email"]
    await db.commit()
    return {"code": 0, "message": "更新成功"}


@router.put("/password", summary="修改密码")
async def change_password(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_user_id(request, db)
    body = await request.json()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    old_pwd = body.get("old_password", "")
    new_pwd = body.get("new_password", "")
    if not verify_password(old_pwd, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="新密码至少6位")
    user.password_hash = hash_password(new_pwd)
    await db.commit()
    return {"code": 0, "message": "密码修改成功"}


@router.delete("/memory", summary="清除我的客服记忆（遗忘权）")
async def erase_memory(request: Request, db: AsyncSession = Depends(get_db)):
    """按个保法要求提供遗忘权：一键清除偏好/向量记忆/会话历史"""
    user_id = await get_user_id(request, db)
    import asyncio

    from app.services.privacy_service import erase_user_data
    result = await asyncio.to_thread(erase_user_data, user_id)
    return {"code": 0, "data": result, "message": "客服记忆已清除"}
