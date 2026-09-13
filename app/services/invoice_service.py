"""电子发票：申请（写，确认闭环）→ 开具（模拟服务商/真实服务商）→ 查询"""
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import InvoiceRequest, Order


class InvoiceService:
    @staticmethod
    def create(db: Session, user_id: int, order_id: int, title: str, tax_no: str, email: str) -> InvoiceRequest:
        order = db.execute(select(Order).where(Order.id == order_id, Order.user_id == user_id)).scalar_one_or_none()
        if not order:
            raise ValueError("订单不存在")
        if order.order_status not in ("completed", "delivered"):
            raise ValueError("订单未完成，暂不能开发票")
        existing = db.execute(select(InvoiceRequest).where(
            InvoiceRequest.order_id == order_id, InvoiceRequest.user_id == user_id,
            InvoiceRequest.status.in_(["created", "processing"]))).scalars().first()
        if existing:
            raise ValueError("该订单已有发票申请在处理中")
        inv = InvoiceRequest(order_id=order.id, user_id=user_id, title=title[:128],
                             tax_no=tax_no[:64], email=email[:128], amount=float(order.pay_amount))
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return inv

    @staticmethod
    def issue(db: Session, inv_id: int) -> dict:
        """开具发票（模拟服务商：生成发票号与下载地址；生产接服务商 API）"""
        inv = db.get(InvoiceRequest, inv_id)
        if not inv:
            raise ValueError("发票申请不存在")
        if inv.status in ("issued", "processing"):
            return {"invoice_no": inv.invoice_no, "status": inv.status}
        inv.status = "issued"
        inv.invoice_no = f"INV{datetime.utcnow().strftime('%Y%m%d')}{secrets.token_hex(4).upper()}"
        inv.file_url = f"/static/invoices/{inv.invoice_no}.pdf"
        inv.issued_at = datetime.utcnow()
        db.commit()
        return {"invoice_no": inv.invoice_no, "file_url": inv.file_url, "status": inv.status}

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[dict]:
        rows = db.execute(select(InvoiceRequest).where(
            InvoiceRequest.user_id == user_id).order_by(InvoiceRequest.id.desc())).scalars().all()
        return [{"id": r.id, "order_id": r.order_id, "title": r.title, "amount": float(r.amount),
                 "status": r.status, "invoice_no": r.invoice_no, "file_url": r.file_url,
                 "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
