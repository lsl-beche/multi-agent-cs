"""C 端订单路由（仅 HTTP 适配）"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user, get_db
from app.services.order_service import OrderService

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


class CreateOrderItem(BaseModel):
    sku_id: int
    quantity: int


class CreateOrderBody(BaseModel):
    items: list[CreateOrderItem]
    address_id: int
    remark: str | None = None
    coupon_id: int | None = None
    idempotency_key: str | None = None


@router.post("", summary="创建订单")
async def create_order(body: CreateOrderBody, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        result = await OrderService.create_order_async(
            db,
            uid,
            [item.model_dump() for item in body.items],
            body.address_id,
            remark=body.remark,
            user_coupon_id=body.coupon_id,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        from app.services.behavior_service import record_async
        for item in result.get("items", []):
            await record_async(db, uid, item["product_id"], "order")
    except Exception:
        pass
    return {"code": 0, "data": result, "message": "下单成功"}


@router.get("", summary="我的订单")
async def list_orders(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    db=Depends(get_db),
):
    uid = await _uid(request)
    items, total = await OrderService.list_orders_async(
        db, page=page, page_size=page_size, order_status=status, user_id=uid
    )
    return {"code": 0, "data": {"items": items, "total": total}}


@router.get("/{order_id}", summary="订单详情")
async def order_detail(order_id: int, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        result = await OrderService.get_order_detail_async(db, order_id, uid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 0, "data": result}


@router.put("/{order_id}/cancel", summary="取消订单")
async def cancel_order(order_id: int, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        result = await OrderService.cancel_order_async(db, order_id, "用户取消", uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": result, "message": "订单已取消"}


@router.put("/{order_id}/confirm", summary="确认收货")
async def confirm_order(order_id: int, request: Request, db=Depends(get_db)):
    uid = await _uid(request)
    try:
        result = await OrderService.confirm_receipt_async(db, order_id, uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": result, "message": "已确认收货"}
