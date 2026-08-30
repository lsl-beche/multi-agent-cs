"""C 端订单路由：下单/列表/详情/取消/确认收货"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import current_user, get_db
from app.models.tables import (
    Address, Order,
)
from app.services.order_service import OrderService

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


def _order_to_dict(order: Order, db: Session) -> dict:
    items = []
    for oi in order.items:
        items.append({
            "id": oi.id,
            "product_id": oi.product_id,
            "product_name": oi.product_name,
            "sku_name": oi.spec_info.get("sku_name", ""),
            "price": float(oi.unit_price),
            "quantity": oi.quantity,
            "image": oi.image_url or "",
        })

    addr = None
    if order.address_id:
        a = db.execute(select(Address).where(Address.id == order.address_id)).scalar_one_or_none()
        if a:
            addr = {
                "receiver_name": a.receiver,
                "receiver_phone": a.phone,
                "province": a.province,
                "city": a.city,
                "district": a.district,
                "detail": a.detail,
            }

    return {
        "id": order.id,
        "order_no": order.order_no,
        "status": order.order_status,
        "pay_status": order.pay_status,
        "total_amount": float(order.total_amount),
        "items": items,
        "address": addr,
        "created_at": str(order.created_at),
        "paid_at": str(order.paid_at) if order.paid_at else None,
        "shipped_at": str(order.shipped_at) if order.shipped_at else None,
        "finished_at": str(order.completed_at) if order.completed_at else None,
    }


# ── 下单 ──

class CreateOrderItem(BaseModel):
    sku_id: int
    quantity: int


class CreateOrderBody(BaseModel):
    items: list[CreateOrderItem]
    address_id: int
    remark: str | None = None
    coupon_id: int | None = None


@router.post("", summary="创建订单")
async def create_order(body: CreateOrderBody, request: Request, db: Session = Depends(get_db)):
    """从购物车/立即购买创建订单"""
    uid = await _uid(request)
    try:
        result = OrderService.create_order(
            db,
            uid,
            [item.model_dump() for item in body.items],
            body.address_id,
            remark=body.remark,
            user_coupon_id=body.coupon_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 领域事件：订单已创建（供指标/通知/数仓消费）
    from app.core.events import publish
    await publish("order.created", {
        "order_id": result["id"],
        "order_no": result["order_no"],
        "user_id": uid,
        "pay_amount": result["pay_amount"],
    })

    # 行为日志：下单
    try:
        from app.services.behavior_service import record
        for item in result["items"]:
            record(db, uid, item["product_id"], "order")
    except Exception:
        pass

    return {"code": 0, "data": result, "message": "下单成功"}


# ── 查询 ──

@router.get("", summary="我的订单")
async def list_orders(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """查询当前用户的订单列表"""
    uid = await _uid(request)
    query = select(Order).where(Order.user_id == uid)
    if status:
        query = query.where(Order.order_status == status)

    total = len(list(db.execute(query).scalars().all()))
    offset = (page - 1) * page_size
    orders = db.execute(query.order_by(Order.id.desc()).offset(offset).limit(page_size)).scalars().all()

    result = [_order_to_dict(o, db) for o in orders]
    return {"code": 0, "data": {"items": result, "total": total}}


@router.get("/{order_id}", summary="订单详情")
async def order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    """查询订单详情"""
    uid = await _uid(request)
    order = db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == uid)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"code": 0, "data": _order_to_dict(order, db)}


# ── 操作 ──

@router.put("/{order_id}/cancel", summary="取消订单")
async def cancel_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    """取消订单并释放库存"""
    uid = await _uid(request)
    order = db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == uid)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.order_status not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    try:
        OrderService.cancel_order(db, order.id, reason="用户取消", operator_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "订单已取消"}


@router.put("/{order_id}/confirm", summary="确认收货")
async def confirm_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    """确认收货"""
    uid = await _uid(request)
    order = db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == uid)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        OrderService.confirm_receipt(db, order.id, operator_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "已确认收货"}
