"""支付对账：本地支付/退款流水一致性核验（沙箱渠道）

目标：每日跑一次，发现"本地记录 vs 订单状态"不一致项，
防范丢单/错单/重复支付。真实渠道接入后，provider 侧补渠道流水比对。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config.settings import settings
from app.core.db import SessionLocal
from app.models.tables import Order, Payment, Refund

logger = logging.getLogger(__name__)


def reconcile(window_hours: int = 24) -> dict:
    """对账窗口内的支付/退款记录，返回差异清单"""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=window_hours)
        payments = db.execute(
            select(Payment).where(Payment.created_at >= since).order_by(Payment.id)
        ).scalars().all()
        refunds = db.execute(
            select(Refund).where(Refund.created_at >= since).order_by(Refund.id)
        ).scalars().all()
        orders = {o.id: o for o in db.execute(select(Order)).scalars().all()}

        mismatches = []
        checked = 0
        for p in payments:
            checked += 1
            o = orders.get(p.order_id)
            if o is None:
                mismatches.append(f"PAY {p.payment_no}: 订单 {p.order_id} 不存在")
                continue
            # 一致性规则：支付成功 → 订单必须已支付且有支付时间
            if p.status == "paid":
                if o.pay_status not in ("paid", "refunded"):
                    mismatches.append(f"PAY {p.payment_no}: 已支付但订单 {o.order_no} pay_status={o.pay_status}")
                if not o.paid_at:
                    mismatches.append(f"PAY {p.payment_no}: 已支付但订单 {o.order_no} 缺 paid_at")
            # 超时未支付：超过支付有效期仍未支付 → 提示（由超时关单任务处理）
            elif p.status == "pending":
                if o.pay_status != "unpaid":
                    mismatches.append(f"PAY {p.payment_no}: 待支付但订单 {o.order_no} pay_status={o.pay_status}")

        for r in refunds:
            checked += 1
            o = orders.get(r.order_id)
            if o is None:
                mismatches.append(f"RF {r.refund_no}: 订单 {r.order_id} 不存在")
                continue
            if r.status in ("processing", "completed") and o.pay_status not in ("refunded",):
                mismatches.append(f"RF {r.refund_no}: 退款 {r.status} 但订单 {o.order_no} pay_status={o.pay_status}")
            if r.status == "completed" and not r.completed_at:
                mismatches.append(f"RF {r.refund_no}: 已到账但缺 completed_at")

        return {
            "window_hours": window_hours,
            "checked": checked,
            "mismatches": mismatches,
            "ok": len(mismatches) == 0,
        }
    finally:
        db.close()
