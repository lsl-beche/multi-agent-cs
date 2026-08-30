"""支付服务：流水查询 + 退款审核"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Payment, Refund


class PaymentService:

    @staticmethod
    def list_payments(db: Session, page: int = 1, page_size: int = 20,
                      status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Payment)
        if status:
            query = query.where(Payment.status == status)
        rows, total = paginate(db, query, page, page_size, order_by=Payment.id.desc())

        result = [{
            "id": p.id, "payment_no": p.payment_no, "order_id": p.order_id,
            "amount": float(p.amount), "channel": p.channel, "trade_no": p.trade_no,
            "status": p.status,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in rows]
        return result, total

    @staticmethod
    def list_refunds(db: Session, page: int = 1, page_size: int = 20,
                     status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Refund)
        if status:
            query = query.where(Refund.status == status)
        rows, total = paginate(db, query, page, page_size, order_by=Refund.id.desc())

        result = [{
            "id": r.id, "refund_no": r.refund_no, "order_id": r.order_id,
            "amount": float(r.amount), "reason": r.reason, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
        return result, total

    @staticmethod
    def get_payment_status_by_order(db: Session, order_no: str) -> dict:
        """按订单号查询支付流水与状态"""
        from app.models.tables import Order

        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单 {order_no}"}
        rows = db.execute(
            select(Payment).where(Payment.order_id == o.id).order_by(Payment.id.desc())
        ).scalars().all()
        return {
            "order_no": order_no,
            "pay_status": o.pay_status,
            "payments": [{
                "payment_no": p.payment_no,
                "amount": float(p.amount),
                "channel": p.channel,
                "status": p.status,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            } for p in rows],
        }

    @staticmethod
    def get_refunds_by_order(db: Session, order_no: str) -> dict:
        """按订单号查询退款进度"""
        from app.models.tables import Order

        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单 {order_no}"}
        rows = db.execute(
            select(Refund).where(Refund.order_id == o.id).order_by(Refund.id.desc())
        ).scalars().all()
        return {
            "order_no": order_no,
            "refunds": [{
                "refund_no": r.refund_no,
                "amount": float(r.amount),
                "reason": r.reason,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            } for r in rows],
        }

    @staticmethod
    def approve_refund(db: Session, refund_id: int, approved: bool,
                       operator_id: int | None = None) -> dict:
        refund = db.execute(select(Refund).where(Refund.id == refund_id)).scalar_one_or_none()
        if not refund:
            raise ValueError("退款记录不存在")
        if refund.status not in ("pending", "processing"):
            raise ValueError(f"退款当前状态为 {refund.status}，无法审核")
        refund.status = "processing" if approved else "rejected"
        if approved:
            refund.approved_by = operator_id
        db.commit()
        return {"id": refund.id, "status": refund.status}

    @staticmethod
    def complete_refund(db: Session, refund_id: int) -> dict:
        """退款到账（沙箱渠道回调/财务确认）：标记完成并更新订单支付状态"""
        refund = db.execute(select(Refund).where(Refund.id == refund_id)).scalar_one_or_none()
        if not refund:
            raise ValueError("退款记录不存在")
        if refund.status != "processing":
            raise ValueError(f"退款当前状态为 {refund.status}，不能标记到账")
        refund.status = "completed"
        refund.completed_at = datetime.utcnow()
        from app.models.tables import Order
        order = db.execute(select(Order).where(Order.id == refund.order_id)).scalar_one_or_none()
        if order:
            order.pay_status = "refunded"
        db.commit()
        return {"id": refund.id, "status": refund.status, "refund_no": refund.refund_no}
