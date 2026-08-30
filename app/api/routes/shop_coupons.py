"""C端优惠券路由：查询/校验"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.services.coupon_service import CouponService

router = APIRouter()


@router.get("/api/user/coupons")
async def list_user_coupons(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    coupons = await CouponService.get_user_coupons_async(db, int(user["sub"]))
    return {"code": 0, "data": coupons}


@router.post("/api/orders/validate-coupon")
async def validate_coupon(req: dict, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await CouponService.validate_coupon_async(db, int(user["sub"]), req["user_coupon_id"], req["order_amount"])
    return {"code": 0, "data": result}
