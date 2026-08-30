"""订单管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.models.schemas import OrderCancelRequest, OrderShipRequest
from app.services.order_service import OrderService

router = APIRouter()


@router.get("", summary="订单列表")
async def list_orders(
    user: dict = Depends(require_permission("orders", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    order_status: str | None = None,
    pay_status: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    data, total = await OrderService.list_orders_async(
        db, page, page_size, order_status=order_status,
    )
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/{order_id}", summary="订单详情")
async def get_order(order_id: int, user: dict = Depends(require_permission("orders", "read")), db: AsyncSession = Depends(get_db)):
    try:
        return {"code": 0, "data": await OrderService.get_order_async(db, order_id)}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.put("/{order_id}/confirm", summary="确认订单")
async def confirm_order(order_id: int, user: dict = Depends(require_permission("orders", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await OrderService.confirm_order_async(db, order_id, int(user["sub"]))
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{order_id}/ship", summary="发货")
async def ship_order(order_id: int, body: OrderShipRequest, user: dict = Depends(require_permission("orders", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await OrderService.ship_order_async(db, order_id, body.carrier, body.tracking_no, int(user["sub"]))
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{order_id}/cancel", summary="取消订单")
async def cancel_order(order_id: int, body: OrderCancelRequest | None = None, user: dict = Depends(require_permission("orders", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await OrderService.cancel_order_async(
            db, order_id, body.reason if body else None, int(user["sub"])
        )
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{order_id}/complete", summary="完成订单")
async def complete_order(order_id: int, user: dict = Depends(require_permission("orders", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await OrderService.complete_order_async(db, order_id, int(user["sub"]))
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
