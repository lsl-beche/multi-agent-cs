"""评价服务：审核/回复"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.tables import Product, Review
from app.repositories import OrderRepository, ReviewRepository
from app.services.async_bridge import async_adapter


class ReviewService:

    @staticmethod
    async def submit_review_async(
        db: AsyncSession,
        user_id: int,
        order_id: int,
        product_id: int,
        rating: int,
        content: str = "",
        is_anonymous: bool = False,
    ) -> dict:
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise ValueError("订单不存在")
        if order.order_status != "completed":
            raise ValueError("订单未完成，无法评价")
        review_repo = ReviewRepository(db)
        existing = await review_repo.get_by_order_product(order_id, product_id)
        if existing:
            raise ValueError("该商品已评价")
        review = Review(
            product_id=product_id,
            order_id=order_id,
            user_id=user_id,
            rating=rating,
            content=content,
            is_anonymous=is_anonymous,
            status="approved",
        )
        await review_repo.add(review)
        await review_repo.commit()
        return {"id": review.id, "message": "评价成功"}

    @staticmethod
    async def list_product_reviews_async(
        db: AsyncSession,
        product_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict], int]:
        repo = ReviewRepository(db)
        rows, total = await repo.list_product(product_id, page, page_size)
        data = [{
            "id": r.id, "rating": r.rating, "content": r.content,
            "is_anonymous": r.is_anonymous, "reply": r.reply,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
        return data, total

    @staticmethod
    def search_reviews(db: Session, keyword: str, limit: int = 3) -> list[dict]:
        """客服工具：按商品关键词搜索已通过的评价"""
        if not keyword:
            return []
        products = db.execute(
            select(Product).where(Product.name.ilike(f"%{keyword}%")).limit(limit)
        ).scalars().all()
        if not products:
            return []
        ids = [p.id for p in products]
        rows = db.execute(
            select(Review)
            .where(Review.product_id.in_(ids), Review.status == "approved")
            .order_by(Review.created_at.desc())
            .limit(limit * 3)
        ).scalars().all()
        name_map = {p.id: p.name for p in products}
        result = []
        for r in rows:
            result.append({
                "product": name_map.get(r.product_id, ""),
                "rating": r.rating,
                "content": (r.content or "")[:200],
                "created_at": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
            })
        return result

    @staticmethod
    def list_reviews(db: Session, page: int = 1, page_size: int = 20,
                     status: str | None = None, product_id: int | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Review)
        if status:
            query = query.where(Review.status == status)
        if product_id:
            query = query.where(Review.product_id == product_id)

        rows, total = paginate(db, query, page, page_size, order_by=Review.id.desc())

        result = [{
            "id": r.id, "product_id": r.product_id, "order_id": r.order_id,
            "rating": r.rating, "content": r.content, "images": r.images,
            "is_anonymous": r.is_anonymous, "status": r.status, "reply": r.reply,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
        return result, total

    @staticmethod
    def approve_review(db: Session, review_id: int, approved: bool) -> dict:
        r = db.execute(select(Review).where(Review.id == review_id)).scalar_one_or_none()
        if not r:
            raise ValueError("评价不存在")
        r.status = "approved" if approved else "rejected"
        db.commit()
        return {"id": r.id, "status": r.status}

    @staticmethod
    def reply_review(db: Session, review_id: int, reply: str) -> dict:
        r = db.execute(select(Review).where(Review.id == review_id)).scalar_one_or_none()
        if not r:
            raise ValueError("评价不存在")
        r.reply = reply
        db.commit()
        return {"id": r.id, "reply": reply}


ReviewService.list_reviews_async = async_adapter(ReviewService.list_reviews)
ReviewService.approve_review_async = async_adapter(ReviewService.approve_review)
ReviewService.reply_review_async = async_adapter(ReviewService.reply_review)
