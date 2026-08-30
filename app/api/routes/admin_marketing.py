"""营销管理路由：优惠券 + 促销活动"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, run_sync
from app.api.middleware.auth import require_permission
from app.models.schemas import CouponCreate, CouponGrantRequest, PromotionCreate
from app.services.coupon_service import CouponService

router = APIRouter()


# ── 优惠券 ──

@router.get("/coupons", summary="优惠券列表")
async def list_coupons(
    user: dict = Depends(require_permission("coupons", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    data, total = await run_sync(db, CouponService.list_coupons, page, page_size)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/coupons", summary="创建优惠券")
async def create_coupon(
    body: CouponCreate,
    user: dict = Depends(require_permission("coupons", "create")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_sync(db, CouponService.create_coupon, body.model_dump())
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/coupons/{coupon_id}", summary="停用优惠券")
async def delete_coupon(
    coupon_id: int,
    user: dict = Depends(require_permission("coupons", "delete")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_sync(db, CouponService.delete_coupon, coupon_id)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.post("/coupons/{coupon_id}/grant", summary="发放优惠券")
async def grant_coupon(
    coupon_id: int,
    body: CouponGrantRequest,
    user: dict = Depends(require_permission("coupons", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_sync(db, CouponService.grant_coupon, coupon_id, body.user_ids)
        return {"code": 0, "data": result, "message": f"已发放 {result['granted']} 张"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# ── 促销活动 ──

@router.get("/promotions", summary="促销活动列表")
async def list_promotions(
    user: dict = Depends(require_permission("promotions", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    data, total = await run_sync(db, CouponService.list_promotions, page, page_size)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/promotions", summary="创建促销活动")
async def create_promotion(
    body: PromotionCreate,
    user: dict = Depends(require_permission("promotions", "create")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_sync(db, CouponService.create_promotion, body.model_dump())
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
