#!/usr/bin/env python3
"""10000 笔并发扣减容量压测(60 身份轮转 + 线程级 Session 连接复用)。

- Session 复用:万级请求若每请求新建连接,TIME_WAIT 会耗尽 Windows 临时端口;
  线程级 keep-alive 会话是压测工具的正确形态
- 断言:非 200 响应为 0、终态 = 初始 - 成功数(零超卖)、吞吐与延迟分位数
"""
import argparse
import concurrent.futures
import json
import sys
import threading
import time
import uuid

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8081")
    ap.add_argument("--sku", type=int, default=1)
    ap.add_argument("--total", type=int, default=10000)
    ap.add_argument("--threads", type=int, default=40)
    ap.add_argument("--identities", type=int, default=60)
    args = ap.parse_args()

    probe = requests.Session()
    r = probe.get(f"{args.base}/api/inventory/{args.sku}", timeout=10).json()
    assert r["code"] == 0, f"读取库存失败: {r}"
    initial = r["data"]["stock"]
    assert initial >= args.total, f"库存不足: {initial} < {args.total},请先补库存"
    print(f"初始库存={initial}  请求={args.total}  线程={args.threads}  身份={args.identities}")

    local = threading.local()
    latencies = []
    errors = []
    lock = threading.Lock()

    def session_for() -> requests.Session:
        if not hasattr(local, "s"):
            local.s = requests.Session()
        return local.s

    def hit(i: int) -> int:
        ident = f"load-{i % args.identities}"
        headers = {
            "Idempotency-Key": str(uuid.uuid4()),
            "X-User-Id": ident,
            "Content-Type": "application/json",
        }
        t0 = time.perf_counter()
        try:
            resp = session_for().post(f"{args.base}/api/inventory/{args.sku}/deduct",
                                      json={"quantity": 1}, headers=headers, timeout=30)
            dt = (time.perf_counter() - t0) * 1000
            with lock:
                latencies.append(dt)
            return resp.status_code
        except Exception as e:
            with lock:
                errors.append(str(e)[:80])
                latencies.append((time.perf_counter() - t0) * 1000)
            return -1

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
        codes = list(pool.map(hit, range(args.total)))
    wall = time.time() - t0

    final = probe.get(f"{args.base}/api/inventory/{args.sku}", timeout=10).json()["data"]["stock"]
    ok = codes.count(200)
    others = {c: codes.count(c) for c in set(codes) if c != 200}

    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2]
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]
    p99 = lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.99))]

    print(f"\n==== 10000 笔压测报告 ====")
    print(f"耗时 {wall:.1f}s | 吞吐 {args.total / wall:.0f} req/s")
    print(f"响应分布: 200×{ok}  其他={others if others else '无'}")
    print(f"延迟 ms: P50={p50:.0f} P95={p95:.0f} P99={p99:.0f} max={lat_sorted[-1]:.0f}")
    print(f"库存守恒: 初始 {initial} - 成功 {ok} = 终态 {final} "
          f"({'PASS 零超卖' if final == initial - ok and final >= 0 else 'FAIL'})")

    passed = (not others) and (final == initial - ok) and (final >= 0)
    print("\nPASS" if passed else "\nFAIL: 存在异常响应或守恒破坏")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
