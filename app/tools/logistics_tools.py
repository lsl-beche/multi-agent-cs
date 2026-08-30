"""物流相关工具：物流追踪

两个工具：
- get_shipment_track：真实数据（读 shipments 表，含归属校验），
  订单/物流查询的主路径
- track_logistics：历史模拟实现（返回【模拟】占位文案），
  保留用于云端模式兼容与下游 API 未就绪时的兜底

生产演进：对接快递100/菜鸟/顺丰开放平台后，
由 logistics_gateway 沙箱升级为真实 Provider 轮询/Webhook 更新。
"""
import json

from langchain_core.tools import tool
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import Order
from app.services import logistics_service
from app.services.shipment_service import ShipmentService
from app.tools.registry import register


@tool
def track_logistics(order_id: str) -> str:
    """物流追踪：根据订单号查询物流单号与最新运输轨迹。参数 order_id 为订单号。"""
    return logistics_service.track_by_order(order_id)


@tool
def get_shipment_track(order_id: str, user_id: str = "") -> str:
    """物流信息查询：根据订单号查询发货单、承运商、快递单号与物流状态（真实数据库数据）。
    参数 order_id 为订单号。"""
    db = SessionLocal()
    try:
        order = db.execute(select(Order).where(Order.order_no == order_id)).scalar_one_or_none()
        if order is None:
            return json.dumps({"error": "not_found", "message": f"未找到订单号 {order_id} 对应的订单"}, ensure_ascii=False)
        if user_id and not str(user_id).startswith("guest_") and str(order.user_id) != str(user_id):
            return json.dumps({"error": "forbidden", "message": "无权查看该订单"}, ensure_ascii=False)
        return json.dumps(ShipmentService.get_shipment_by_order_no(db, order_id), ensure_ascii=False)
    finally:
        db.close()


register(track_logistics)
register(get_shipment_track)
