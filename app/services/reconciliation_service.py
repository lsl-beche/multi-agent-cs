"""支付/退款对账服务（原生异步）"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Order, Payment, Refund


async def reconcile(
    db: AsyncSession,
    window_hours: int = 24,
) -> dict:
    since = datetime.utcnow() - timedelta(hours=window_hours)
    payments = (await db.execute(
        select(Payment).where(Payment.created_at >= since).order_by(Payment.id)
    )).scalars().all()
    refunds = (await db.execute(
        select(Refund).where(Refund.created_at >= since).order_by(Refund.id)
    )).scalars().all()
    orders = {o.id: o for o in (await db.execute(select(Order))).scalars().all()}

    mismatches: list[str] = []
    checked = 0

    for p in payments:
        checked += 1
        o = orders.get(p.order_id)
        if o is None:
            mismatches.append(f"PAY {p.payment_no}: 订单 {p.order_id} 不存在")
            continue
        if p.status == "paid":
            if o.pay_status not in ("paid", "refunded"):
                mismatches.append(f"PAY {p.payment_no}: 已支付但订单 {o.order_no} pay_status={o.pay_status}")
            if not o.paid_at:
                mismatches.append(f"PAY {p.payment_no}: 已支付但订单 {o.order_no} 缺 paid_at")
        elif p.status == "pending" and o.pay_status != "unpaid":
            mismatches.append(f"PAY {p.payment_no}: 待支付但订单 {o.order_no} pay_status={o.pay_status}")

    for r in refunds:
        checked += 1
        o = orders.get(r.order_id)
        if o is None:
            mismatches.append(f"RF {r.refund_no}: 订单 {r.order_id} 不存在")
            continue
        if r.status in ("processing", "completed") and o.pay_status != "refunded":
            mismatches.append(f"RF {r.refund_no}: 退款 {r.status} 但订单 {o.order_no} pay_status={o.pay_status}")
        if r.status == "completed" and not r.completed_at:
            mismatches.append(f"RF {r.refund_no}: 已到账但缺 completed_at")

    return {
        "window_hours": window_hours,
        "checked": checked,
        "mismatches": mismatches,
        "ok": len(mismatches) == 0,
    }
