"""写操作工具：取消订单/确认收货/申请退款/修改地址（提案→确认→执行闭环）

每个写操作都是"成对"工具：
- propose_*：生成提案并写入 Redis 待办（action_store.set_pending），
  附带校验（归属/订单状态/支付流水/已有退款）—— 只"打算做"，不落地
- execute_*：用户确认后由 workflow.confirm_action 节点调用，真正执行——
  每个执行工具会重新做归属与状态校验（防过期/越权），并返回结构化结果

依赖的订单服务能力：
- 取消：OrderService.cancel_order（流转 cancelled + 释放库存）
- 收货：OrderService.confirm_receipt（shipped→delivered→completed）
- 退款：创建 Refund 记录（pending，待管理员审核→到账）
- 改址：新建 Address 记录并挂到订单（结构化地址解析为阶段二优化项）
"""
import json
import secrets
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import select

from app.core.db import SessionLocal
from app.dialogue.action_store import set_pending
from app.models.tables import Address, Order, Payment, Refund
from app.services.order_service import OrderService
from app.tools.registry import register


def _find_order(db, order_no: str):
    return db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()


def _owner_ok(order, user_id: str) -> bool:
    if not user_id or str(user_id).startswith("guest_"):
        return True
    return order is not None and order.user_id is not None and str(order.user_id) == str(user_id)


def _ok(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _err(msg: str) -> str:
    return json.dumps({"error": "failed", "message": msg}, ensure_ascii=False)


def _propose(session_id: str, action: str, params: dict, tip: str) -> str:
    """通用提案落库：写入待办 + 返回结构化的"待确认"提示"""
    set_pending(session_id, action, params)
    return _ok({
        "proposal": action,
        "status": "pending_confirmation",
        "tip": tip,
        "message": "请回复“确认”以执行，回复“取消”可放弃。",
    })


# ── 取消订单 ──

@tool
def propose_cancel_order(order_id: str, user_id: str = "", reason: str = "", session_id: str = "") -> str:
    """取消订单【写操作-需用户确认】：生成取消订单提案，用户确认后执行并释放库存。"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        if order.order_status not in ("pending", "confirmed"):
            return _err(f"订单当前状态为 {order.order_status}，无法取消")
        return _propose(session_id, "cancel_order",
                        {"order_id": order_id, "user_id": user_id, "reason": reason[:200]},
                        f"将为订单 {order_id} 发起取消申请")
    finally:
        db.close()


@tool
def execute_cancel_order(order_id: str, user_id: str = "", reason: str = "") -> str:
    """执行取消订单（确认闭环的第二步，由系统调用）"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        try:
            result = OrderService.cancel_order(db, order.id, reason or "用户申请取消")
            return _ok({**result, "message": "订单已取消，库存已释放"})
        except ValueError as e:
            return _err(str(e))
    finally:
        db.close()


# ── 确认收货 ──

@tool
def propose_confirm_receipt(order_id: str, user_id: str = "", session_id: str = "") -> str:
    """确认收货【写操作-需用户确认】：生成确认收货提案，用户确认后订单流转为已完成。"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        if order.order_status not in ("shipped", "delivered"):
            return _err(f"订单当前状态为 {order.order_status}，暂不能确认收货")
        return _propose(session_id, "confirm_receipt",
                        {"order_id": order_id, "user_id": user_id},
                        f"将为订单 {order_id} 确认收货")
    finally:
        db.close()


@tool
def execute_confirm_receipt(order_id: str, user_id: str = "") -> str:
    """执行确认收货（确认闭环的第二步，由系统调用）"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        try:
            result = OrderService.confirm_receipt(db, order.id)
            return _ok({**result, "message": "已确认收货，订单完成，欢迎评价"})
        except ValueError as e:
            return _err(str(e))
    finally:
        db.close()


# ── 申请退款 ──

@tool
def propose_apply_refund(order_id: str, user_id: str = "", reason: str = "", session_id: str = "") -> str:
    """申请退款【写操作-需用户确认】：生成退款申请提案，用户确认后创建退款记录。"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        pay = db.execute(select(Payment).where(Payment.order_id == order.id, Payment.status == "paid")).scalars().first()
        if pay is None:
            return _err("该订单没有已支付流水，无法申请退款")
        existing = db.execute(select(Refund).where(Refund.order_id == order.id, Refund.status.in_(["pending", "processing"]))).scalars().first()
        if existing:
            return _err(f"该订单已有退款在处理中（{existing.refund_no}）")
        return _propose(session_id, "apply_refund",
                        {"order_id": order_id, "user_id": user_id, "reason": reason[:200]},
                        f"将为订单 {order_id} 申请退款 ¥{float(order.pay_amount or 0):.2f}")
    finally:
        db.close()


@tool
def execute_apply_refund(order_id: str, user_id: str = "", reason: str = "") -> str:
    """执行退款申请（确认闭环的第二步，由系统调用）：创建退款记录"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        pay = db.execute(select(Payment).where(Payment.order_id == order.id, Payment.status == "paid")).scalars().first()
        if pay is None:
            return _err("该订单没有已支付流水，无法申请退款")
        refund = Refund(
            refund_no=f"RF{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3).upper()}",
            payment_id=pay.id,
            order_id=order.id,
            amount=float(order.pay_amount or 0),
            reason=reason or "用户申请退款",
            status="pending",
        )
        db.add(refund)
        db.commit()
        db.refresh(refund)
        return _ok({"refund_no": refund.refund_no, "amount": float(refund.amount), "status": refund.status,
                    "message": "退款申请已提交，将按售后流程审核"})
    finally:
        db.close()


# ── 修改地址 ──

@tool
def propose_address_change(order_id: str, new_address: str, user_id: str = "", session_id: str = "") -> str:
    """修改收货地址【写操作-需用户确认】：生成改址提案，用户确认后更新订单收货地址。"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        if not new_address or len(new_address) < 5:
            return _err("请提供完整的新收货地址")
        return _propose(session_id, "address_change",
                        {"order_id": order_id, "new_address": new_address, "user_id": user_id},
                        f"将订单 {order_id} 的收货地址修改为：{new_address}")
    finally:
        db.close()


@tool
def execute_address_change(order_id: str, new_address: str, user_id: str = "") -> str:
    """执行改址（确认闭环的第二步，由系统调用）：新建地址记录并挂到订单"""
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return _err(f"未找到订单号 {order_id}")
        if not _owner_ok(order, user_id):
            return _err("无权操作该订单")
        try:
            uid = int(user_id) if user_id and not str(user_id).startswith("guest_") else (order.user_id or 0)
        except (TypeError, ValueError):
            uid = order.user_id or 0
        addr = Address(
            user_id=uid,
            receiver="",
            phone="",
            province="",
            city="",
            district="",
            detail=new_address[:256],
            is_default=False,
        )
        db.add(addr)
        db.flush()
        order.address_id = addr.id
        db.commit()
        return _ok({"order_id": order_id, "address_id": addr.id, "new_address": new_address,
                    "message": "收货地址已更新"})
    finally:
        db.close()


register(propose_cancel_order)
register(execute_cancel_order)
register(propose_confirm_receipt)
register(execute_confirm_receipt)
register(propose_apply_refund)
register(execute_apply_refund)
register(propose_address_change)
register(execute_address_change)
