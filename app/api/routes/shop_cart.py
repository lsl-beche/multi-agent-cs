"""C 端购物车路由（仅 HTTP 适配，业务逻辑在 CartService）"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user, get_db, run_sync
from app.models.schemas import CartQuantityRequest, CartSelectRequest
from app.services.cart_service import CartService

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


@router.get("", summary="获取购物车")
async def get_cart(request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    return {"code": 0, "data": {"items": await CartService.get_cart(db, uid)}}


class AddCartBody(BaseModel):
    sku_id: int
    quantity: int = 1


@router.post("", summary="加入购物车")
async def add_to_cart(body: AddCartBody, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        await CartService.add(db, uid, body.sku_id, body.quantity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        from app.services.behavior_service import record
        await run_sync(db, record, uid, body.sku_id, "cart")
    except Exception:
        pass
    return {"code": 0, "message": "已加入购物车"}


@router.put("/{item_id}", summary="更新数量")
async def update_item(item_id: int, body: CartQuantityRequest, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        await CartService.update(db, uid, item_id, body.quantity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 0, "message": "已更新"}


@router.delete("/{item_id}", summary="删除")
async def remove_item(item_id: int, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        await CartService.remove(db, uid, item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 0, "message": "已删除"}


@router.put("/select-all", summary="全选/取消全选")
async def select_all(body: CartSelectRequest, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    await CartService.select_all(db, uid, body.selected)
    return {"code": 0, "message": "ok"}


@router.put("/{item_id}/select", summary="选中某条")
async def select_one(item_id: int, body: CartSelectRequest, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    await CartService.select_one(db, uid, item_id, body.selected)
    return {"code": 0, "message": "ok"}
