#!/usr/bin/env python3
"""双服务联通冒烟:模拟 Python 智能层经 REST 驱动 Java 交易层的完整写链路。

流程 = 查库存 → 原子扣减(幂等重放验证)→ 为 pending 订单生成取消提案
     → 用户"确认" → 副作用落库(订单 cancelled)。

重跑前需重置数据(幂等键唯一、订单状态不可逆):
  UPDATE skus SET stock=30 WHERE id=2;
  UPDATE orders SET order_status='pending', cancelled_at=NULL WHERE order_no='SO-DIFF-B';
  DELETE FROM pending_actions WHERE session_id LIKE 'agent%';
"""
import sys
import uuid

sys.path.insert(0, "integration")
from agent_client import OrderServiceClient  # noqa: E402


def main() -> int:
    c = OrderServiceClient("http://localhost:8081", user_id="1")
    passed = True

    # 1. 查询联通
    order = c.get_order(3)["data"]
    assert order["orderStatus"] == "pending", f"前置失败:订单 3 应为 pending,先重置数据"
    s0 = c.get_stock(2)["data"]["stock"]

    # 2. 原子扣减 + 幂等重放
    key = str(uuid.uuid4())
    r1 = c.deduct(2, 1, idem_key=key)
    r2 = c.deduct(2, 1, idem_key=key)
    replayed = r2.get("code") == 0 and r1 == r2
    delta = s0 - c.get_stock(2)["data"]["stock"]
    print(f"[扣减+重放] r1={r1.get('code')} replay一致={r1 == r2} delta={delta}")
    passed &= (r1.get("code") == 0 and replayed and delta == 1)

    # 3. 提案 → 确认 → 订单取消
    p = c.create_cancel_proposal(3, "agent-smoke")
    assert p["code"] == 0 and p["data"]["status"] == "PENDING", p
    done = c.confirm(p["data"]["id"])
    order_after = c.get_order(3)["data"]
    print(f"[提案确认] action={done['data']['status']} 订单终态={order_after['orderStatus']}")
    passed &= (done["data"]["status"] == "DONE" and order_after["orderStatus"] == "cancelled")

    print("PASS: Python 智能层 ↔ Java 交易层 全链路联通" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
