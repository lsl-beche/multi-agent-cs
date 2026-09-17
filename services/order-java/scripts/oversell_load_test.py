#!/usr/bin/env python3
"""500 并发零超卖压测驱动 + 守恒断言(order-java 原子扣减)。

把 README 里的「500 并发零超卖」从目标变成可复现的真结果。流程:
  1. 将目标 SKU 库存重置为 S(默认 100,< 并发用户数 U=500);
  2. 启动 Locust,拉起 U 个独立买家(唯一 X-User-Id),每人恰好一次扣减;
  3. 读取 Locust 落盘的状态码计数 + 终态库存;
  4. 断言守恒律(与 concurrency_deduct_test.py 同口径):
       other == 0                      无意外响应码
       success*qty == initial - final  每份被扣的库存都有对应成功请求(无幽灵扣减)
       final >= 0                      零超卖
     并额外要求 attempts == U(500 个请求确实都发出了)。
     库存被精确耗尽(success == initial 且 final == 0)与无 429 作为观测项报告。

前置:docker compose 起 mysql(order-mysql),order-java 跑在 --base(默认 :8081)。
用法:
  python scripts/oversell_load_test.py                       # 500 并发 / 库存 100 / SKU 1
  python scripts/oversell_load_test.py --users 500 --stock 50
  python scripts/oversell_load_test.py --skip-setup          # 库存已手工设好,不重置
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]            # services/order-java
LOCUSTFILE = ROOT / "tests" / "load" / "oversell_locustfile.py"

MYSQL_CONTAINER = "order-mysql"
MYSQL_USER = "root"
MYSQL_PASSWORD = "order_dev_2026"
MYSQL_DB = "order_service"


def read_stock_db(container: str, sku_id: int) -> int:
    """从 MySQL 直读库存(守恒律的唯一权威真值)。

    不能用 GET /api/inventory:读路径是 Cache Aside(InventoryService.getStock),
    缓存只被服务自身写操作 evict;驱动用 docker exec 带外重置库存不会触发 evict,
    HTTP 读会拿到上一个压测残留的旧值,导致 initial 测不准。
    """
    out = subprocess.run(
        ["docker", "exec", container, "mysql",
         f"-u{MYSQL_USER}", f"-p{MYSQL_PASSWORD}", MYSQL_DB, "-N", "-e",
         f"SELECT stock FROM skus WHERE id={int(sku_id)};"],
        capture_output=True, text=True, check=True).stdout
    val = out.strip().splitlines()[-1].strip()
    return int(val)


def get_stock(base: str, sku_id: int) -> int:
    """HTTP 读库存(仅作交叉核对,不作为断言真值——见 read_stock_db 说明)。"""
    r = requests.get(f"{base}/api/inventory/{sku_id}", timeout=10).json()
    assert r.get("code") == 0, f"读取库存失败: {r}"
    return r["data"]["stock"]


def set_stock(container: str, sku_id: int, stock: int) -> None:
    """经 docker exec 直连 MySQL 重置库存(服务端未暴露改库存的写接口)。"""
    sql = f"UPDATE skus SET stock={int(stock)} WHERE id={int(sku_id)};"
    cmd = ["docker", "exec", container, "mysql",
           f"-u{MYSQL_USER}", f"-p{MYSQL_PASSWORD}", MYSQL_DB, "-e", sql]
    print(f"设置库存: SKU {sku_id} -> {stock}")
    subprocess.run(cmd, check=True)


def run_locust(base: str, users: int, spawn_rate: int, run_time: str,
               sku_id: int, qty: int, result_path: Path) -> int:
    env = os.environ.copy()
    env["OVERSELL_SKU_ID"] = str(sku_id)
    env["OVERSELL_QTY"] = str(qty)
    env["OVERSELL_RESULT"] = str(result_path)
    cmd = [sys.executable, "-m", "locust", "-f", str(LOCUSTFILE),
           "--host", base, "--headless",
           "-u", str(users), "-r", str(spawn_rate), "-t", run_time,
           "--only-summary"]
    print("运行:", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8081")
    ap.add_argument("--sku-id", type=int, default=1)
    ap.add_argument("--stock", type=int, default=100, help="初始库存 S,应 < --users")
    ap.add_argument("--qty", type=int, default=1, help="单次扣减数量(服务端上限 100)")
    ap.add_argument("--users", type=int, default=500, help="并发虚拟用户数")
    ap.add_argument("--spawn-rate", type=int, default=500, help="每秒拉起用户数")
    ap.add_argument("--run-time", default="15s", help="压测窗口,需 >= 拉起全部用户耗时")
    ap.add_argument("--mysql-container", default=MYSQL_CONTAINER)
    ap.add_argument("--skip-setup", action="store_true", help="不重置库存(已手工设置)")
    args = ap.parse_args()

    if args.stock >= args.users:
        print(f"WARN: stock({args.stock}) >= users({args.users}),无法制造库存争用;"
              f"建议 stock < users(如 100 < 500)。")

    if not args.skip_setup:
        set_stock(args.mysql_container, args.sku_id, args.stock)

    initial = read_stock_db(args.mysql_container, args.sku_id)
    print(f"initial stock (DB) = {initial}")
    http_initial = get_stock(args.base, args.sku_id)
    if http_initial != initial:
        print(f"  注: HTTP GET 返回 {http_initial} 与 DB {initial} 不一致——"
              f"符合预期(读路径 Cache Aside 缓存未被带外写 evict);断言以 DB 为准。")

    with tempfile.TemporaryDirectory() as td:
        result_path = Path(td) / "tally.json"
        run_locust(args.base, args.users, args.spawn_rate, args.run_time,
                   args.sku_id, args.qty, result_path)
        if not result_path.exists():
            print("FAIL: Locust 未写出结果文件(可能未正常结束或 locustfile 路径错误)")
            return 1
        tally = json.loads(result_path.read_text(encoding="utf-8"))

    final = read_stock_db(args.mysql_container, args.sku_id)

    success = tally["200"]
    conflict = tally["409"]
    limited = tally["429"]
    other = tally["other"]
    attempts = tally["attempts"]

    print("\n=== 结果 ===")
    print(f"并发用户 = {args.users}  每人 {args.qty} 件  总尝试 = {attempts}")
    print(f"200 成功 = {success}   409 拒绝 = {conflict}   "
          f"429 限流 = {limited}   其他 = {other}")
    print(f"initial = {initial}   final = {final}")
    print(f"守恒校验: success*qty({success * args.qty}) == "
          f"initial-final({initial - final})")

    conservation = (other == 0
                    and success * args.qty == initial - final
                    and final >= 0)
    all_fired = attempts == args.users
    drained = success == initial and final == 0

    passed = conservation and all_fired
    print("\nPASS: 零超卖,库存守恒" if passed else "\nFAIL: 超卖或账目不平!")
    if not all_fired:
        print(f"  注: 实际尝试 {attempts} != 用户数 {args.users}"
              f"(部分用户未成功发起请求,可增大 --run-time 或降低 --spawn-rate)。")
    if conservation and not drained:
        print("  注: 守恒成立,但库存未精确耗尽——通常因 429 限流使成功数 < 初始库存。")
    if limited:
        print(f"  注: 出现 {limited} 次 429。唯一 X-User-Id 下单次扣减不应触发限流,"
              f"请检查 RateLimitFilter 身份维度或窗口配置。")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
