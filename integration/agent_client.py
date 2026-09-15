#!/usr/bin/env python3
"""CSagent(Python 智能层)调用 Java 订单服务的集成客户端。

这就是 order_agent.py 工具函数未来接入的样子:
    client = OrderServiceClient(base_url)
    client.deduct(sku_id, qty)                    # 库存扣减(自动幂等键)
    client.create_cancel_proposal(order_id, sid)  # 写操作只生成提案
    client.confirm(action_id)                     # 用户确认后才执行

语义约定:
- 所有写操作自动携带 Idempotency-Key(UUID);遇 409 IDEMPOTENCY_PROCESSING
  可带同键重试;2xx 且 Idempotent-Replayed=true 表示命中回放,结果与首次一致。
"""
import uuid

import requests


class OrderServiceClient:

    def __init__(self, base_url: str = "http://localhost:8081", user_id: str = "1", timeout: int = 10):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["X-User-Id"] = user_id

    def _post(self, path: str, payload: dict | None = None, idem_key: str | None = None):
        headers = {"Content-Type": "application/json"}
        if idem_key is None:
            idem_key = str(uuid.uuid4())
        headers["Idempotency-Key"] = idem_key
        return self.session.post(f"{self.base}{path}", json=payload, headers=headers, timeout=self.timeout)

    # ---- 查询 ----
    def get_order(self, order_id: int) -> dict:
        return self.session.get(f"{self.base}/api/orders/{order_id}", timeout=self.timeout).json()

    def get_stock(self, sku_id: int) -> dict:
        return self.session.get(f"{self.base}/api/inventory/{sku_id}", timeout=self.timeout).json()

    # ---- 写操作 ----
    def deduct(self, sku_id: int, quantity: int, idem_key: str | None = None) -> dict:
        return self._post(f"/api/inventory/{sku_id}/deduct", {"quantity": quantity}, idem_key).json()

    def create_cancel_proposal(self, order_id: int, session_id: str, idem_key: str | None = None) -> dict:
        return self._post(f"/api/orders/{order_id}/cancel-proposal",
                          {"sessionId": session_id, "userId": int(self.session.headers["X-User-Id"])},
                          idem_key).json()

    def confirm(self, action_id: int, idem_key: str | None = None) -> dict:
        return self._post(f"/api/pending-actions/{action_id}/confirm", {}, idem_key).json()

    def cancel_proposal(self, action_id: int, idem_key: str | None = None) -> dict:
        return self._post(f"/api/pending-actions/{action_id}/cancel", {}, idem_key).json()
