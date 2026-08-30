"""售后相关工具：退款进度、工单进度查询

- get_refund_status：按订单号查退款申请/审核/到账状态（含归属校验）
- get_ticket_status：按工单号查售后/转人工工单处理状态（含归属校验）

归属校验规则：游客（guest_*）放行；登录用户必须与记录 owner 一致，
防止通过"知道订单号/工单号"越权查看他人数据。
"""
import json

from langchain_core.tools import tool
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import Order, Ticket
from app.services.payment_service import PaymentService
from app.tools.registry import register


def _find_order(db, order_no: str):
    return db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()


@tool
def get_refund_status(order_id: str, user_id: str = "") -> str:
    """退款进度查询：根据订单号查询退款申请、审核状态与到账时间。参数 order_id 为订单号。"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return json.dumps({"error": "not_found", "message": f"未找到订单号 {order_id} 对应的订单"}, ensure_ascii=False)
        if user_id and not str(user_id).startswith("guest_") and str(order.user_id) != str(user_id):
            return json.dumps({"error": "forbidden", "message": "无权查看该订单"}, ensure_ascii=False)
        return json.dumps(PaymentService.get_refunds_by_order(db, order_id), ensure_ascii=False)
    finally:
        db.close()


@tool
def get_ticket_status(ticket_id: str, user_id: str = "") -> str:
    """工单进度查询：根据工单号查询售后/转人工工单的处理状态。参数 ticket_id 为工单号。"""
    db = SessionLocal()
    try:
        t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if t is None:
            return json.dumps({"error": "not_found", "message": f"未找到工单 {ticket_id}"}, ensure_ascii=False)
        if user_id and not str(user_id).startswith("guest_") and t.user_id and str(t.user_id) != str(user_id):
            return json.dumps({"error": "forbidden", "message": "无权查看该工单"}, ensure_ascii=False)
        return json.dumps({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": (t.description or "")[:200],
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }, ensure_ascii=False)
    finally:
        db.close()


register(get_refund_status)
register(get_ticket_status)
