"""C 端购物车路由"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db, run_sync
from app.models.tables import CartItem, Product, Sku

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


def _cart_item_to_dict(item: CartItem, sku: Sku | None, product: Product | None) -> dict:
    return {
        "id": item.id,
        "product_id": product.id if product else 0,
        "product_name": product.name if product else "",
        "sku_id": item.sku_id,
        "sku_name": sku.sku_code if sku else "",
        "price": float(sku.price) if sku else 0,
        "quantity": item.quantity,
        "image": product.main_image or "",
        "stock": 999,  # 简化：从 inventory 表查太复杂，前端不需要精确库存
        "selected": item.selected,
    }


@router.get("", summary="获取购物车")
async def get_cart(request: Request, db: AsyncSession = Depends(get_db)):
    """获取当前用户的购物车"""
    uid = await _uid(request)
    items = (await db.execute(
        select(CartItem).where(CartItem.user_id == uid).order_by(CartItem.id.desc())
    )).scalars().all()

    result = []
    for item in items:
        sku = (await db.execute(select(Sku).where(Sku.id == item.sku_id))).scalar_one_or_none()
        product = (await db.execute(select(Product).where(Product.id == sku.product_id))).scalar_one_or_none() if sku else None
        result.append(_cart_item_to_dict(item, sku, product))

    return {"code": 0, "data": {"items": result}}


class AddCartBody(BaseModel):
    sku_id: int
    quantity: int = 1


@router.post("", summary="加入购物车")
async def add_to_cart(body: AddCartBody, request: Request, db: AsyncSession = Depends(get_db)):
    """添加商品到购物车"""
    uid = await _uid(request)

    sku = (await db.execute(select(Sku).where(Sku.id == body.sku_id))).scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")

    # 检查是否已有同一 SKU
    existing = (await db.execute(
        select(CartItem).where(CartItem.user_id == uid, CartItem.sku_id == body.sku_id)
    )).scalar_one_or_none()

    if existing:
        existing.quantity += body.quantity
    else:
        db.add(CartItem(user_id=uid, sku_id=body.sku_id, quantity=body.quantity, selected=True))

    await db.commit()

    # 行为日志：加购
    try:
        from app.services.behavior_service import record
        await run_sync(db, record, uid, sku.product_id, "cart")
    except Exception:
        pass

    return {"code": 0, "message": "已加入购物车"}


@router.put("/{item_id}", summary="更新数量")
async def update_item(item_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """更新购物车项数量"""
    uid = await _uid(request)
    body = await request.json()
    qty = body.get("quantity", 1)
    item = (await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == uid)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="购物车项不存在")
    item.quantity = max(1, qty)
    await db.commit()
    return {"code": 0, "message": "已更新"}


@router.delete("/{item_id}", summary="删除")
async def remove_item(item_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """删除购物车项"""
    uid = await _uid(request)
    item = (await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == uid)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="购物车项不存在")
    db.delete(item)
    await db.commit()
    return {"code": 0, "message": "已删除"}


@router.put("/select-all", summary="全选/取消全选")
async def select_all(request: Request, db: AsyncSession = Depends(get_db)):
    """切换全选状态"""
    uid = await _uid(request)
    body = await request.json()
    selected = bool(body.get("selected", True))
    await db.execute(update(CartItem).where(CartItem.user_id == uid).values(selected=selected))
    await db.commit()
    return {"code": 0, "message": "ok"}


@router.put("/{item_id}/select", summary="选中某条")
async def select_one(item_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """切换单条选中状态"""
    uid = await _uid(request)
    body = await request.json()
    selected = bool(body.get("selected", True))
    await db.execute(
        update(CartItem).where(CartItem.id == item_id, CartItem.user_id == uid).values(selected=selected)
    )
    await db.commit()
    return {"code": 0, "message": "ok"}
