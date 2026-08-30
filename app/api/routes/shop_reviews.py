from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, current_user
from app.models.tables import Review, Order, OrderItem
from app.services.review_service import ReviewService

router = APIRouter()

@router.post("/api/reviews")
async def submit_review(req: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    """用户提交商品评价"""
    order_id = req.get("order_id")
    product_id = req.get("product_id")
    rating = req.get("rating")
    content = req.get("content", "")
    is_anonymous = req.get("is_anonymous", False)
    
    # 校验：订单属于该用户且已完成
    uid = int(user["sub"])
    if order_id:
        order = db.execute(select(Order).where(Order.id == order_id, Order.user_id == uid)).scalar_one_or_none()
        if not order:
            raise HTTPException(404, "订单不存在")
        if order.order_status != "completed":
            raise HTTPException(400, "订单未完成，无法评价")
        
        # 校验：未重复评价
        existing = db.execute(select(Review).where(Review.order_id == order_id, Review.product_id == product_id)).scalar_one_or_none()
        if existing:
            raise HTTPException(400, "该商品已评价")
    
    review = Review(
        product_id=product_id, order_id=order_id, user_id=uid,
        rating=rating, content=content, is_anonymous=is_anonymous, status="approved"
    )
    db.add(review)
    db.commit()

    # 行为日志：评价
    try:
        from app.services.behavior_service import record
        record(db, uid, product_id, "review")
    except Exception:
        pass

    return {"code": 0, "data": {"id": review.id, "message": "评价成功"}}


@router.get("/api/reviews/product/{product_id}")
async def get_product_reviews(product_id: int, page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    """获取商品评价列表（仅已审核通过的）"""
    offset = (page - 1) * page_size
    reviews = db.execute(
        select(Review).where(Review.product_id == product_id, Review.status == "approved")
        .order_by(Review.created_at.desc()).offset(offset).limit(page_size)
    ).scalars().all()
    total = len(db.execute(select(Review).where(Review.product_id == product_id, Review.status == "approved")).scalars().all())
    
    data = [{
        "id": r.id, "rating": r.rating, "content": r.content,
        "is_anonymous": r.is_anonymous, "reply": r.reply,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in reviews]
    return {"code": 0, "data": {"items": data, "total": total, "page": page, "page_size": page_size}}
