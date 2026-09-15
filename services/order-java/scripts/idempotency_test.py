#!/usr/bin/env python3
"""幂等键验证:串行重放 / 同键并发 / 键体不匹配。

守恒律:同一 Idempotency-Key 的 N 次请求,业务副作用只发生一次
(扣减恰为 1),且所有 2xx 响应体完全一致(回放语义)。
"""
import argparse
import concurrent.futures
import json
import sys
import uuid

import requests


def post(base, sku, key, qty=1):
    return requests.post(f"{base}/api/inventory/{sku}/deduct",
                         headers={"Idempotency-Key": key, "Content-Type": "application/json"},
                         json={"quantity": qty}, timeout=10)


def stock(base, sku):
    return requests.get(f"{base}/api/inventory/{sku}", timeout=5).json()["data"]["stock"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8081")
    ap.add_argument("--sku", type=int, default=2)
    args = ap.parse_args()

    passed = True

    # 1. 串行重放:同键两次,副作用一次,响应一致
    s0 = stock(args.base, args.sku)
    key = str(uuid.uuid4())
    r1, r2 = post(args.base, args.sku, key), post(args.base, args.sku, key)
    same_body = r1.text == r2.text and r2.headers.get("Idempotent-Replayed") == "true"
    delta = s0 - stock(args.base, args.sku)
    print(f"[串行重放] delta={delta} 响应一致={same_body}")
    passed &= (delta == 1 and same_body and r1.status_code == 200)

    # 2. 键体不匹配:同键不同 quantity → 40002
    r3 = post(args.base, args.sku, key, qty=2)
    print(f"[键体不匹配] code={r3.json().get('code')} (期望 40002)")
    passed &= (r3.json().get("code") == 40002)

    # 3. 同键 20 并发:副作用恰一次
    s1 = stock(args.base, args.sku)
    ckey = str(uuid.uuid4())
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        rs = list(pool.map(lambda _: post(args.base, args.sku, ckey), range(20)))
    final = stock(args.base, args.sku)
    delta = s1 - final
    bodies = {r.text for r in rs if r.status_code == 200}
    codes = sorted({r.status_code for r in rs})
    print(f"[同键并发] delta={delta} 响应码={codes} 200响应体种数={len(bodies)}")
    passed &= (delta == 1 and len(bodies) <= 1)

    print("PASS: 幂等语义成立" if passed else "FAIL: 幂等被破坏!")
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        print(__doc__)
        sys.exit(0)
    sys.exit(main())
