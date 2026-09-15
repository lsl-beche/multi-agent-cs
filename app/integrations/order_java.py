"""Java 交易服务客户端:写链路切流开关(安全审查修复 P0-2)。

设置环境变量 ORDER_SERVICE_URL(如 http://localhost:8081)后,取消订单的
执行切到 Java 交易服务——提案-确认走原子状态机 + 幂等键,并发的重复"确认"
恰好执行一次(竞态缺陷已在 Java 侧修复,对拍证据见 services/order-java/README.md)。

未设置时保持本地 execute_* 旧路径,零破坏兼容。
Java 服务接口契约:services/order-java/README.md。
"""
import os
import uuid

import requests

_BASE = os.getenv("ORDER_SERVICE_URL", "").rstrip("/")
_TIMEOUT = 10


def java_enabled() -> bool:
    return bool(_BASE)


def create_order(sku_id: int, quantity: int, user_id: str, remark: str = "") -> dict:
    """商城下单:Java 侧原子扣减 + 订单/商品行落库。购物车多品多次调用(拆单)。"""
    uid = int(user_id) if user_id.isdigit() else 1
    r = requests.post(f"{_BASE}/api/orders",
                      json={"userId": uid, "skuId": sku_id, "quantity": quantity, "buyerRemark": remark},
                      headers={"Idempotency-Key": str(uuid.uuid4())}, timeout=_TIMEOUT).json()
    if r.get("code") != 0:
        raise RuntimeError(f"下单失败: {r.get('message')}")
    return r["data"]


def mark_paid_via_java(order_no: str, trade_no: str, amount: float) -> None:
    """支付回调的状态变更:Java 侧金额强校验(资损防护)+ 条件迁移(重放幂等)。"""
    lookup = requests.get(f"{_BASE}/api/orders/by-no/{order_no}", timeout=_TIMEOUT).json()
    if lookup.get("code") != 0:
        raise RuntimeError(f"订单查询失败: {lookup.get('message')}")
    r = requests.post(f"{_BASE}/api/orders/{lookup['data']}/paid",
                      json={"tradeNo": trade_no, "amount": amount}, timeout=_TIMEOUT).json()
    if r.get("code") != 0:
        raise RuntimeError(f"支付标记失败: {r.get('message')}")


def order_status_json(order_no: str, user_id: str = "") -> str:
    """订单状态 JSON(供 order_agent 查询工具切流,输出与本地工具同构)。"""
    import json
    detail = order_detail_dict(order_no)
    return json.dumps({
        "order_no": detail["orderNo"], "status": detail["orderStatus"],
        "pay_status": detail["payStatus"], "pay_amount": detail["payAmount"],
        "created_at": detail["createdAt"],
    }, ensure_ascii=False)


def order_detail_json(order_no: str, user_id: str = "") -> str:
    import json
    detail = order_detail_dict(order_no)
    return json.dumps({
        "order_no": detail["orderNo"], "status": detail["orderStatus"],
        "pay_status": detail["payStatus"], "total_amount": detail["totalAmount"],
        "pay_amount": detail["payAmount"], "items": detail.get("items", []),
        "created_at": detail["createdAt"],
    }, ensure_ascii=False)


def order_detail_dict(order_no: str) -> dict:
    lookup = requests.get(f"{_BASE}/api/orders/by-no/{order_no}", timeout=_TIMEOUT).json()
    if lookup.get("code") != 0:
        raise RuntimeError(f"订单查询失败: {lookup.get('message')}")
    return requests.get(f"{_BASE}/api/orders/{lookup['data']}", timeout=_TIMEOUT).json()["data"]


def cancel_order_via_java(order_no: str, user_id: str = "1") -> str:
    """取消订单:提案 + 确认两步在 Java 侧原子完成。

    返回与本地 execute_cancel_order 同构的 JSON 串,workflow 的话术映射无需改动。
    请求携带 Idempotency-Key:网络重试不会造成重复取消。
    """
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    uid = int(user_id) if user_id.isdigit() else 1

    lookup = requests.get(f"{_BASE}/api/orders/by-no/{order_no}",
                          headers=headers, timeout=_TIMEOUT).json()
    if lookup.get("code") != 0:
        raise RuntimeError(f"订单查询失败: {lookup.get('message')}")
    order_id = lookup["data"]

    proposal = requests.post(f"{_BASE}/api/orders/{order_id}/cancel-proposal",
                             json={"sessionId": f"java-{uuid.uuid4().hex[:8]}", "userId": uid},
                             headers=headers, timeout=_TIMEOUT).json()
    if proposal.get("code") != 0:
        raise RuntimeError(f"创建提案失败: {proposal.get('message')}")
    action_id = proposal["data"]["id"]

    confirmed = requests.post(f"{_BASE}/api/pending-actions/{action_id}/confirm",
                              headers=headers, timeout=_TIMEOUT).json()
    if confirmed.get("code") != 0 or confirmed.get("data", {}).get("status") != "DONE":
        raise RuntimeError(f"确认执行失败: {confirmed.get('message')}")

    return f'{{"ok": true, "order_id": "{order_no}", "status": "cancelled"}}'
