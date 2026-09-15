#!/usr/bin/env python3
"""并发扣减验证:断言零超卖 + 库存守恒。

守恒律(全部满足才 PASS):
  1. 无 200/409 之外的响应码(other == 0)
  2. success × qty == initial - final   (每一份被记账的库存都有对应成功请求)
  3. final >= 0                          (零超卖)

用法:
  python scripts/concurrency_deduct_test.py --sku-id 1 --qty 1 --threads 20
建议先在 DB 把目标 SKU stock 设为小于线程数(如 10),以验证"部分成功部分拒绝"。
"""
import argparse
import concurrent.futures
import sys

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8081")
    ap.add_argument("--sku-id", type=int, default=1)
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--threads", type=int, default=20)
    args = ap.parse_args()

    sess = requests.Session()
    r = sess.get(f"{args.base}/api/inventory/{args.sku_id}", timeout=5).json()
    assert r["code"] == 0, f"读取初始库存失败: {r}"
    initial = r["data"]["stock"]

    def hit(_: int) -> int:
        resp = requests.post(
            f"{args.base}/api/inventory/{args.sku_id}/deduct",
            json={"quantity": args.qty}, timeout=10)
        return resp.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
        codes = list(pool.map(hit, range(args.threads)))

    success, conflict = codes.count(200), codes.count(409)
    limited = codes.count(429)
    other = len(codes) - success - conflict - limited

    final = sess.get(f"{args.base}/api/inventory/{args.sku_id}", timeout=5).json()["data"]["stock"]

    print(f"initial={initial}  requests={args.threads}x{args.qty}  "
          f"success={success}  conflict409={conflict}  limited429={limited}  other={other}")
    print(f"final={final}  守恒校验: success*qty({success * args.qty}) == initial-final({initial - final})")

    # 429 为限流主动拒绝,未执行扣减,不影响守恒
    passed = (other == 0
              and success * args.qty == initial - final
              and final >= 0)
    print("PASS: 零超卖,库存守恒" if passed else "FAIL: 超卖或账目不平!")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
