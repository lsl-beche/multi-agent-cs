"""C端优惠券路由：查询/校验"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, current_user
from app.services.coupon_service import CouponService

router = APIRouter()


@router.get("/api/user/coupons")
async def list_user_coupons(user=Depends(current_user), db: Session = Depends(get_db)):
    coupons = CouponService.get_user_coupons(db, int(user["sub"]))
    return {"code": 0, "data": coupons}


@router.post("/api/orders/validate-coupon")
async def validate_coupon(req: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    result = CouponService.validate_coupon(db, int(user["sub"]), req["user_coupon_id"], req["order_amount"])
    return {"code": 0, "data": result}
