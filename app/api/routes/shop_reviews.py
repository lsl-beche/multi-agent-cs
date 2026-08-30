"""C 端评价路由（仅 HTTP 适配）"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import current_user, get_db, run_sync
from app.models.schemas import ReviewSubmitRequest
from app.services.review_service import ReviewService

router = APIRouter()


@router.post("/api/reviews")
async def submit_review(body: ReviewSubmitRequest, user=Depends(current_user), db=Depends(get_db)):
    uid = int(user["sub"])
    try:
        result = await ReviewService.submit_review_async(
            db,
            uid,
            body.order_id,
            body.product_id,
            body.rating,
            body.content,
            body.is_anonymous,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    try:
        from app.services.behavior_service import record
        await run_sync(db, record, uid, body.product_id, "review")
    except Exception:
        pass
    return {"code": 0, "data": result}


@router.get("/api/reviews/product/{product_id}")
async def get_product_reviews(product_id: int, page: int = 1, page_size: int = 10, db=Depends(get_db)):
    items, total = await ReviewService.list_product_reviews_async(db, product_id, page, page_size)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}
