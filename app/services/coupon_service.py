"""营销服务：优惠券CRUD + 领券/核销"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Coupon, Promotion, User, UserCoupon


class CouponService:

    @staticmethod
    def get_my_coupons(db: Session, user_id: int, status: str = "unused") -> list[dict]:
        """查询用户指定状态的优惠券（含券详情）"""
        rows = db.execute(
            select(Coupon, UserCoupon)
            .join(UserCoupon, UserCoupon.coupon_id == Coupon.id)
            .where(UserCoupon.user_id == user_id, UserCoupon.status == status)
            .order_by(UserCoupon.id.desc())
        ).all()
        result = []
        for c, uc in rows:
            result.append({
                "user_coupon_id": uc.id,
                "coupon_id": c.id,
                "name": c.name,
                "coupon_type": c.coupon_type,
                "threshold": float(c.threshold),
                "value": float(c.value),
                "end_time": c.end_time.isoformat() if c.end_time else None,
            })
        return result

    @staticmethod
    def claim_coupon(db: Session, user_id: int, coupon_id: int) -> dict:
        """领取优惠券：校验有效期/库存/上限后发放"""
        coupon = db.execute(select(Coupon).where(Coupon.id == coupon_id)).scalar_one_or_none()
        if not coupon:
            raise ValueError("优惠券不存在")
        if coupon.status != "active":
            raise ValueError("优惠券已失效")
        now = datetime.utcnow()
        if now < coupon.start_time or now > coupon.end_time:
            raise ValueError("不在优惠券领取时间内")
        if coupon.used_count >= coupon.total_count:
            raise ValueError("优惠券已领完")
        cnt = db.execute(
            select(func.count(UserCoupon.id)).where(
                UserCoupon.user_id == user_id,
                UserCoupon.coupon_id == coupon_id,
            )
        ).scalar() or 0
        if cnt >= coupon.user_limit:
            raise ValueError("已达该券领取上限")
        uc = UserCoupon(user_id=user_id, coupon_id=coupon_id, status="unused")
        db.add(uc)
        coupon.used_count += 1
        db.commit()
        db.refresh(uc)
        return {"user_coupon_id": uc.id, "coupon_id": coupon_id, "name": coupon.name, "status": "unused"}

    @staticmethod
    def list_coupons(db: Session, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Coupon)
        rows, total = paginate(db, query, page, page_size, order_by=Coupon.id.desc())

        result = [{
            "id": c.id, "name": c.name, "coupon_type": c.coupon_type,
            "threshold": float(c.threshold), "value": float(c.value),
            "total_count": c.total_count, "used_count": c.used_count,
            "user_limit": c.user_limit, "status": c.status,
            "start_time": c.start_time.isoformat() if c.start_time else None,
            "end_time": c.end_time.isoformat() if c.end_time else None,
        } for c in rows]
        return result, total

    @staticmethod
    def create_coupon(db: Session, data: dict) -> dict:
        coupon = Coupon(
            name=data["name"],
            coupon_type=data["coupon_type"],
            threshold=data.get("threshold", 0),
            value=data["value"],
            total_count=data["total_count"],
            user_limit=data.get("user_limit", 1),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
        )
        db.add(coupon)
        db.commit()
        return {"id": coupon.id, "name": coupon.name}

    @staticmethod
    def delete_coupon(db: Session, coupon_id: int) -> dict:
        c = db.execute(select(Coupon).where(Coupon.id == coupon_id)).scalar_one_or_none()
        if not c:
            raise ValueError("优惠券不存在")
        c.status = "inactive"
        db.commit()
        return {"id": c.id, "status": c.status}

    @staticmethod
    def grant_coupon(db: Session, coupon_id: int, user_ids: list[int]) -> dict:
        coupon = db.execute(select(Coupon).where(Coupon.id == coupon_id)).scalar_one_or_none()
        if not coupon:
            raise ValueError("优惠券不存在")
        if coupon.status != "active":
            raise ValueError("优惠券已停用")

        granted = 0
        for uid in user_ids:
            user = db.execute(select(User).where(User.id == uid)).scalar_one_or_none()
            if not user:
                continue
            # 检查限领
            count = db.execute(
                select(UserCoupon).where(
                    UserCoupon.user_id == uid,
                    UserCoupon.coupon_id == coupon_id,
                )
            ).scalars().all()
            if len(count) >= coupon.user_limit:
                continue
            if coupon.used_count >= coupon.total_count:
                break

            db.add(UserCoupon(user_id=uid, coupon_id=coupon_id))
            coupon.used_count += 1
            granted += 1

        db.commit()
        return {"granted": granted, "coupon_id": coupon_id}

    # ── C端用户优惠券 ──

    @staticmethod
    def get_user_coupons(db: Session, user_id: int) -> list[dict]:
        """获取用户未使用的优惠券（含模板详情）"""
        rows = db.execute(
            select(UserCoupon, Coupon)
            .join(Coupon, UserCoupon.coupon_id == Coupon.id)
            .where(UserCoupon.user_id == user_id, UserCoupon.status == "unused")
            .order_by(UserCoupon.id.desc())
        ).all()

        result = []
        for uc, c in rows:
            result.append({
                "id": uc.id,
                "coupon_id": c.id,
                "name": c.name,
                "coupon_type": c.coupon_type,
                "threshold": float(c.threshold),
                "value": float(c.value),
                "status": uc.status,
                "start_time": c.start_time.isoformat() if c.start_time else None,
                "end_time": c.end_time.isoformat() if c.end_time else None,
                "created_at": uc.created_at.isoformat() if uc.created_at else None,
            })
        return result

    @staticmethod
    def validate_coupon(db: Session, user_id: int, user_coupon_id: int, order_amount: float) -> dict:
        """校验用户优惠券：存在性、归属、未过期、未使用、满减门槛、库存"""
        now = datetime.utcnow()

        row = db.execute(
            select(UserCoupon, Coupon)
            .join(Coupon, UserCoupon.coupon_id == Coupon.id)
            .where(UserCoupon.id == user_coupon_id)
        ).one_or_none()

        if not row:
            return {"valid": False, "discount": 0, "message": "优惠券不存在"}
        uc, c = row

        if uc.user_id != user_id:
            return {"valid": False, "discount": 0, "message": "优惠券不属于当前用户"}
        if uc.status != "unused":
            return {"valid": False, "discount": 0, "message": "优惠券已使用或已过期"}
        if c.status != "active":
            return {"valid": False, "discount": 0, "message": "优惠券已停用"}
        if now < c.start_time:
            return {"valid": False, "discount": 0, "message": "优惠券尚未生效"}
        if now > c.end_time:
            return {"valid": False, "discount": 0, "message": "优惠券已过期"}
        if c.used_count >= c.total_count:
            return {"valid": False, "discount": 0, "message": "优惠券已领完"}
        if float(order_amount) < float(c.threshold):
            return {"valid": False, "discount": 0, "message": f"订单金额未满足满{float(c.threshold):.0f}元条件"}

        # 计算折扣
        if c.coupon_type == "fixed":
            discount = float(c.value)
        elif c.coupon_type == "percent":
            discount = round(float(order_amount) * float(c.value) / 100, 2)
        else:
            discount = 0

        discount = min(discount, float(order_amount))

        return {
            "valid": True,
            "discount": discount,
            "coupon": {
                "id": c.id,
                "name": c.name,
                "coupon_type": c.coupon_type,
                "threshold": float(c.threshold),
                "value": float(c.value),
            },
            "message": "优惠券可用",
        }

    # ── 促销活动 ──

    @staticmethod
    def list_promotions(db: Session, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Promotion)
        rows, total = paginate(db, query, page, page_size, order_by=Promotion.id.desc())

        result = [{
            "id": p.id, "name": p.name, "promo_type": p.promo_type,
            "rules": p.rules, "product_ids": p.product_ids,
            "status": p.status,
            "start_time": p.start_time.isoformat() if p.start_time else None,
            "end_time": p.end_time.isoformat() if p.end_time else None,
        } for p in rows]
        return result, total

    @staticmethod
    def create_promotion(db: Session, data: dict) -> dict:
        p = Promotion(
            name=data["name"],
            promo_type=data["promo_type"],
            rules=data["rules"],
            product_ids=data.get("product_ids", []),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
        )
        db.add(p)
        db.commit()
        return {"id": p.id, "name": p.name}
