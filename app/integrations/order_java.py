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


def java_write_enabled() -> bool:
    return bool(_BASE)


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
