"""评价管理路由：审核/回复"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.models.schemas import ReviewReplyRequest
from app.services.review_service import ReviewService

router = APIRouter()


@router.get("", summary="评价列表")
async def list_reviews(
    user: dict = Depends(require_permission("reviews", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    product_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    data, total = await ReviewService.list_reviews_async(db, page, page_size, status, product_id)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.put("/{review_id}/approve", summary="通过评价")
async def approve_review(review_id: int, user: dict = Depends(require_permission("reviews", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await ReviewService.approve_review_async(db, review_id, True)
        return {"code": 0, "data": result, "message": "审核通过"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{review_id}/reject", summary="驳回评价")
async def reject_review(review_id: int, user: dict = Depends(require_permission("reviews", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await ReviewService.approve_review_async(db, review_id, False)
        return {"code": 0, "data": result, "message": "已驳回"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{review_id}/reply", summary="回复评价")
async def reply_review(
    review_id: int,
    body: ReviewReplyRequest,
    user: dict = Depends(require_permission("reviews", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ReviewService.reply_review_async(db, review_id, body.reply)
        return {"code": 0, "data": result, "message": "回复成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
