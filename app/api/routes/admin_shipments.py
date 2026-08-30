"""物流管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, run_sync
from app.api.middleware.auth import require_permission
from app.services.shipment_service import ShipmentService

router = APIRouter()


class ShipmentTrackRequest(BaseModel):
    tracking_no: str = Field(..., min_length=1)
    carrier: str | None = None


@router.get("", summary="物流列表")
async def list_shipments(
    user: dict = Depends(require_permission("shipments", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    data, total = await run_sync(db, ShipmentService.list_shipments, page, page_size, order_id, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.put("/{shipment_id}/track", summary="更新物流追踪")
async def update_tracking(
    shipment_id: int,
    body: ShipmentTrackRequest,
    user: dict = Depends(require_permission("shipments", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_sync(db, ShipmentService.update_tracking, shipment_id, body.tracking_no, body.carrier)
        return {"code": 0, "data": result, "message": "物流已更新"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
