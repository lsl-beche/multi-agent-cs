"""发票工具：申请/查询（客服 Agent 用）"""
import json

from langchain_core.tools import tool

from app.core.db import SessionLocal
from app.services.invoice_service import InvoiceService
from app.tools.registry import register


@tool
def request_invoice(user_id: str, order_id: int, title: str, tax_no: str = "", email: str = "") -> str:
    """申请开发票【写操作-需用户确认】：订单完成后生成发票申请。"""
    db = SessionLocal()
    try:
        inv = InvoiceService.create(db, int(user_id), order_id, title, tax_no, email)
        return json.dumps({"id": inv.id, "status": inv.status, "message": "发票申请已提交"}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


@tool
def get_invoice_status(user_id: str) -> str:
    """发票状态查询：返回用户全部发票申请及状态。"""
    db = SessionLocal()
    try:
        return json.dumps(InvoiceService.list_by_user(db, int(user_id)), ensure_ascii=False)
    finally:
        db.close()


register(request_invoice)
register(get_invoice_status)
