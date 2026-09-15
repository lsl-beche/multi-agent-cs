#!/usr/bin/env python3
"""对拍:原子状态迁移 vs check-then-act(legacy,复刻 Python 侧缺陷)。

准备(每次运行前注入一对新订单+提案,SQL):
  INSERT INTO orders (order_no,user_id,total_amount,discount_amount,pay_amount,order_status)
    VALUES ('SO-DIFF-<n>',1,1.00,0,1.00,'pending');
  INSERT INTO pending_actions (session_id,user_id,action_type,order_id,status,expires_at)
    VALUES ('diff',1,'CANCEL_ORDER',LAST_INSERT_ID(),'PENDING',NOW() + INTERVAL 10 MINUTE);

判定:
  atomic 模式:PASS = 恰好 1 笔 200,其余 409,且副作用执行次数 executions == 1;
  legacy 模式:预期复现竞态,executions >= 2(多次"确认"都执行了副作用)。
"""
import argparse
import concurrent.futures
import sys

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8081")
    ap.add_argument("--action-id", type=int, required=True)
    ap.add_argument("--order-id", type=int, required=True)
    ap.add_argument("--mode", choices=["atomic", "legacy"], default="atomic")
    ap.add_argument("--threads", type=int, default=20)
    args = ap.parse_args()

    path = (f"/api/debug/pending-actions/{args.action_id}/confirm-legacy"
            if args.mode == "legacy" else
            f"/api/pending-actions/{args.action_id}/confirm")

    def hit(_: int) -> int:
        return requests.post(f"{args.base}{path}", timeout=10).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
        codes = list(pool.map(hit, range(args.threads)))

    ok = codes.count(200)
    conflict = codes.count(409)
    other = len(codes) - ok - conflict

    probe = requests.get(
        f"{args.base}/api/debug/side-effect",
        params={"orderId": args.order_id, "actionId": args.action_id}, timeout=5).json()["data"]

    print(f"mode={args.mode}  200={ok}  409={conflict}  other={other}")
    print(f"orderVersion={probe['orderVersion']}  orderStatus={probe['orderStatus']}  "
          f"actionStatus={probe['actionStatus']}  副作用执行次数={probe['executions']}")

    if args.mode == "atomic":
        passed = ok == 1 and probe["executions"] == 1 and probe["actionStatus"] == "DONE"
        print("PASS: 原子抢占,副作用恰好执行一次" if passed else "FAIL: 原子路径仍出现重复执行!")
        return 0 if passed else 1

    reproduced = probe["executions"] >= 2
    print("REPRODUCED: check-then-act 竞态复现,副作用被重复执行"
          if reproduced else "未复现(窗口未被踩中,可调大 sleep 重跑)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
