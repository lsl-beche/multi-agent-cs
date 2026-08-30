"""库存管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.models.schemas import InventoryAdjustRequest
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("", summary="库存列表")
async def list_inventory(
    user: dict = Depends(require_permission("inventory", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    low_stock_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    data, total = await InventoryService.list_inventory_async(db, page, page_size, keyword, low_stock_only)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/adjust", summary="调整库存")
async def adjust_inventory(body: InventoryAdjustRequest, user: dict = Depends(require_permission("inventory", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await InventoryService.adjust_inventory_async(db, body.sku_id, body.change_qty, body.reason)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/logs", summary="库存流水")
async def get_logs(
    user: dict = Depends(require_permission("inventory", "read")),
    sku_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    data, total = await InventoryService.get_logs_async(db, sku_id, page, page_size)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}
