"""促销工具：优惠券查询/领取、积分查询、会员信息

供促销 Agent 使用（本地规则驱动 + 云端 tool-calling）：
- get_my_coupons：我的未使用券（含详情）
- claim_coupon：领券（写操作；校验有效期/库存/次数上限）
- get_points：积分查询
- get_member_info：会员等级（按积分阈值推导）

所有工具都要求登录用户（int uid）；游客返回"请先登录"提示。
"""
import json

from langchain_core.tools import tool

from app.core.db import SessionLocal
from app.services.coupon_service import CouponService
from app.services.user_service import UserService
from app.tools.registry import register


def _uid(user_id: str) -> int | None:
    """登录用户才可查；游客返回 None"""
    if not user_id or str(user_id).startswith("guest_"):
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@tool
def get_my_coupons(user_id: str) -> str:
    """我的优惠券查询：返回当前用户未使用的优惠券列表。参数 user_id 为用户ID。"""
    uid = _uid(user_id)
    if uid is None:
        return json.dumps({"message": "请先登录后再查询优惠券"}, ensure_ascii=False)
    db = SessionLocal()
    try:
        return json.dumps(CouponService.get_my_coupons(db, uid), ensure_ascii=False)
    finally:
        db.close()


@tool
def claim_coupon(user_id: str, coupon_id: int) -> str:
    """领取优惠券【写操作】：为用户领取指定优惠券。参数 coupon_id 为优惠券ID。"""
    uid = _uid(user_id)
    if uid is None:
        return json.dumps({"error": "auth_required", "message": "请先登录后再领取优惠券"}, ensure_ascii=False)
    db = SessionLocal()
    try:
        return json.dumps(CouponService.claim_coupon(db, uid, coupon_id), ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": "claim_failed", "message": str(e)}, ensure_ascii=False)
    finally:
        db.close()


@tool
def get_points(user_id: str) -> str:
    """积分查询：返回当前用户可用积分。参数 user_id 为用户ID。"""
    uid = _uid(user_id)
    if uid is None:
        return json.dumps({"message": "请先登录后再查询积分"}, ensure_ascii=False)
    db = SessionLocal()
    try:
        return json.dumps(UserService.get_points(db, uid), ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


@tool
def get_member_info(user_id: str) -> str:
    """会员等级查询：返回当前用户的会员等级与积分。参数 user_id 为用户ID。"""
    uid = _uid(user_id)
    if uid is None:
        return json.dumps({"message": "请先登录后再查询会员信息"}, ensure_ascii=False)
    db = SessionLocal()
    try:
        return json.dumps(UserService.get_member_info(db, uid), ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


register(get_my_coupons)
register(claim_coupon)
register(get_points)
register(get_member_info)
