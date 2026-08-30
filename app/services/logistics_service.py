"""物流服务：物流信息追踪（对接电商物流微服务）"""
import json


def track_by_order(order_id: str) -> str:
    # TODO: data = gateway_client.get(f"/logistics/track", params={"order_id": order_id})
    return f"【模拟】订单 {order_id} 物流追踪：业务API待对接（GET /logistics/track?order_id=）"


def track_by_express(express_no: str, carrier: str = "") -> str:
    try:
        from app.services.logistics_gateway import get_logistics_provider
        provider = get_logistics_provider()
        data = provider.track(express_no, None, carrier)
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return f"【模拟】快递单号 {express_no} 轨迹查询：业务API未配置或调用失败。"
