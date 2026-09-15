"""订单相关工具：订单/支付查询（含归属校验）

工具清单：
- query_order：基础状态查询（订单状态/金额/支付）
- get_order_detail：完整详情（商品明细/支付/物流/日志）
- get_payment_status：支付流水状态（补齐"支付异常"意图）

安全设计（_owner_ok）：
游客（guest_*）放行；登录用户必须与订单 owner 一致，否则返回"无权查看"。
订单号由调用方先正则抽取，工具内不再解析（职责单一）。

注：改地址提案已迁移到 action_tools.py（写操作统一闭环）。
"""
import json

from langchain_core.tools import tool
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import Order
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.tools.registry import register


def _find_order(db, order_no: str) -> Order | None:
    return db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()


def _owner_ok(order: Order, user_id: str) -> bool:
    """订单归属校验：游客（guest_）不校验；登录用户必须与订单 owner 一致"""
    if not user_id or str(user_id).startswith("guest_"):
        return True
    return order is not None and order.user_id is not None and str(order.user_id) == str(user_id)


def _forbidden() -> str:
    return json.dumps({"error": "forbidden", "message": "无权查看该订单"}, ensure_ascii=False)


@tool
def query_order(order_id: str, user_id: str = "") -> str:
    """订单状态查询：根据订单号查询订单状态、金额、收货信息。参数 order_id 为订单号。"""
    from app.integrations.order_java import java_enabled, order_status_json
    if java_enabled():
        # 订单域归一:交易数据以 Java 为唯一事实源,查询经 API
        return order_status_json(order_id, user_id)
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return json.dumps({"error": "not_found", "message": f"未找到订单号 {order_id} 对应的订单"}, ensure_ascii=False)
        if not _owner_ok(order, user_id):
            return _forbidden()
        return json.dumps(OrderService.get_order_status(db, order_id), ensure_ascii=False)
    finally:
        db.close()


@tool
def get_order_detail(order_id: str, user_id: str = "") -> str:
    """订单详情查询：返回订单的商品明细、金额、支付流水、物流单与操作日志。参数 order_id 为订单号。"""
    from app.integrations.order_java import java_enabled, order_detail_json
    if java_enabled():
        return order_detail_json(order_id, user_id)
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return json.dumps({"error": "not_found", "message": f"未找到订单号 {order_id} 对应的订单"}, ensure_ascii=False)
        if not _owner_ok(order, user_id):
            return _forbidden()
        return json.dumps(OrderService.get_order_by_no(db, order_id), ensure_ascii=False)
    finally:
        db.close()


@tool
def get_payment_status(order_id: str, user_id: str = "") -> str:
    """支付状态查询：根据订单号查询支付流水与支付状态（待支付/已支付/退款中）。参数 order_id 为订单号。"""
    from app.integrations.order_java import java_enabled, order_status_json
    if java_enabled():
        return order_status_json(order_id, user_id)
    db = SessionLocal()
    try:
        order = _find_order(db, order_id)
        if order is None:
            return json.dumps({"error": "not_found", "message": f"未找到订单号 {order_id} 对应的订单"}, ensure_ascii=False)
        if not _owner_ok(order, user_id):
            return _forbidden()
        return json.dumps(PaymentService.get_payment_status_by_order(db, order_id), ensure_ascii=False)
    finally:
        db.close()


register(query_order)
register(get_order_detail)
register(get_payment_status)
