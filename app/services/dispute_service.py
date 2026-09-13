"""售后仲裁：退款被拒/争议升级 → 仲裁（举证 → 判定 → 联动退款）"""
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Dispute, Order, Refund
from app.services.payment_service import PaymentService


class DisputeService:
    @staticmethod
    def create(db: Session, user_id: int, order_id: int, reason: str, evidence: dict | None = None) -> Dispute:
        order = db.execute(select(Order).where(Order.id == order_id, Order.user_id == user_id)).scalar_one_or_none()
        if not order:
            raise ValueError("订单不存在")
        refund = db.execute(select(Refund).where(
            Refund.order_id == order_id, Refund.status == "rejected")).scalars().first()
        if not refund:
            raise ValueError("该订单无被拒绝的退款记录，不能发起仲裁")
        d = Dispute(dispute_no=f"DS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}",
                    refund_id=refund.id, order_id=order.id, user_id=user_id,
                    reason=reason[:500], evidence=evidence or {},
                    status="pending")
        db.add(d)
        db.commit()
        db.refresh(d)
        return d

    @staticmethod
    def resolve(db: Session, dispute_id: int, approved: bool, resolution: str) -> dict:
        """管理员判定：通过 → 联动退款到 processing；拒绝 → 维持 rejected"""
        d = db.get(Dispute, dispute_id)
        if not d:
            raise ValueError("仲裁不存在")
        if d.status != "pending":
            raise ValueError(f"仲裁状态为 {d.status}，不能重复判定")
        d.status = "resolved" if approved else "rejected"
        d.resolution = resolution[:500]
        d.resolved_at = datetime.utcnow()
        if approved and d.refund_id:
            PaymentService.approve_refund(db, d.refund_id, True)
        db.commit()
        db.refresh(d)
        return {"dispute_no": d.dispute_no, "status": d.status, "resolution": d.resolution}

    @staticmethod
    def get_status(db: Session, user_id: int, dispute_no: str) -> dict | None:
        d = db.execute(select(Dispute).where(Dispute.dispute_no == dispute_no,
                                             Dispute.user_id == user_id)).scalar_one_or_none()
        if not d:
            return None
        return {"dispute_no": d.dispute_no, "status": d.status, "reason": d.reason,
                "resolution": d.resolution,
                "created_at": d.created_at.isoformat() if d.created_at else None}

    @staticmethod
    def list_pending(db: Session) -> list[dict]:
        rows = db.execute(select(Dispute).where(Dispute.status == "pending").order_by(Dispute.id)).scalars().all()
        return [{"id": r.id, "dispute_no": r.dispute_no, "order_id": r.order_id, "user_id": r.user_id,
                 "reason": r.reason, "evidence": r.evidence, "status": r.status} for r in rows]
