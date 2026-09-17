"""500 并发零超卖压测(Locust)——order-java 原子扣减守恒验证

负载模型:每个虚拟用户 = 一个独立买家(唯一 X-User-Id),整个压测窗口内只发起一次扣减。
  - 唯一 X-User-Id 天然绕开 RateLimitFilter 的「15 次/10s 单身份」限流,
    500 个请求全部落到 DB 的原子 UPDATE ... WHERE stock>=n,制造真实争用;
  - 「每人一次」使总尝试数 == 用户数,守恒断言的账目可精确对齐。
预期(库存 S < 用户数 U):恰好 S 次 200、U-S 次 409、终态库存 0、绝不超卖。

由 scripts/oversell_load_test.py 驱动,通过环境变量传参:
  OVERSELL_SKU_ID   目标 SKU(默认 1)
  OVERSELL_QTY      单次扣减数量(默认 1,服务端上限 100)
  OVERSELL_RESULT   状态码计数 JSON 的落盘路径(必填,压测结束时写出)

单独运行示例:
  OVERSELL_RESULT=/tmp/tally.json \
    locust -f tests/load/oversell_locustfile.py --host http://localhost:8081 \
    --headless -u 500 -r 500 -t 15s
"""

from __future__ import annotations

import itertools
import json
import os
import threading

from locust import HttpUser, constant, events, task

SKU_ID = int(os.getenv("OVERSELL_SKU_ID", "1"))
QTY = int(os.getenv("OVERSELL_QTY", "1"))
RESULT_PATH = os.getenv("OVERSELL_RESULT", "")

# 唯一买家序号:保证每个虚拟用户拥有独立的限流身份桶。
_user_seq = itertools.count(1)
_lock = threading.Lock()
# 200 成功扣减 / 409 库存不足拒绝 / 429 限流 / other 意外码(必须为 0)。
_tally = {"200": 0, "409": 0, "429": 0, "other": 0, "attempts": 0}


def _record(code: int) -> None:
    with _lock:
        _tally["attempts"] += 1
        key = str(code) if code in (200, 409, 429) else "other"
        _tally[key] += 1


@events.test_stop.add_listener
def _dump_tally(**_kwargs) -> None:
    """压测结束时把状态码计数落盘,供驱动脚本做守恒断言。"""
    if not RESULT_PATH:
        return
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(_tally, f, ensure_ascii=False, indent=2)


class OversellUser(HttpUser):
    """on_start 时发起唯一一次扣减,之后空转维持用户存活到压测窗口结束。"""

    # 用户存活期间空转的间隔;扣减只在 on_start 发生一次,故此处仅避免忙等。
    wait_time = constant(5)

    def on_start(self) -> None:
        uid = f"loadtest-{next(_user_seq)}"
        with self.client.post(
            f"/api/inventory/{SKU_ID}/deduct",
            json={"quantity": QTY},
            headers={"X-User-Id": uid},
            catch_response=True,
            name="/api/inventory/[sku]/deduct",
        ) as resp:
            _record(resp.status_code)
            # 200/409/429 均为业务预期结果,不计入 Locust 失败率:
            # 409 是库存耗尽后的正常拒绝,429 是限流主动拒绝,都不是系统错误。
            if resp.status_code in (200, 409, 429):
                resp.success()
            else:
                resp.failure(f"unexpected status {resp.status_code}")

    @task
    def idle(self) -> None:
        # 扣减已在 on_start 完成;此处保持用户在线,直到 -t 窗口结束触发 test_stop。
        return
