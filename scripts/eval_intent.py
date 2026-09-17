#!/usr/bin/env python3
"""意图识别离线评测(生产实践:golden set 回归)

评测集:data/eval/intent_eval.jsonl
  - 12 类意图 × 每类 6 条真实查询变体 = 72 条
  - OOS(超出域)样本 18 条,期望 confidence < 0.5(拒识→关键词兜底)

指标:
  - Accuracy(非 OOS 样本)
  - 分意图 Recall(每类 6 条中命中的比例)
  - OOS 拒识率(confidence < 0.5 判定为"不置信"的比例)
  - 单条平均延迟(生产容量参考)

用法:
  python scripts/eval_intent.py                # 全量
  python scripts/eval_intent.py --limit 30     # 抽样快跑
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dialogue.intent import IntentClassifier  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/eval/intent_eval.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="抽样条数,0=全量")
    args = ap.parse_args()

    cases = [json.loads(line) for line in
             Path(args.data).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[:args.limit]

    clf = IntentClassifier()
    print(f"评测集 {len(cases)} 条,分类器就绪,开始...\n")

    correct = oos_total = oos_rejected = 0
    per_intent = defaultdict(lambda: [0, 0])   # intent -> [hit, total]
    latencies = []
    misses = []

    for i, case in enumerate(cases):
        query, expected = case["query"], case["expected"]
        t0 = time.perf_counter()
        result = clf.classify(query)
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)

        if expected == "__oos__":
            oos_total += 1
            if result.confidence < 0.5:
                oos_rejected += 1
            else:
                misses.append(f"[OOS 未拒识] {query!r} -> {result.name} ({result.confidence:.2f})")
        else:
            per_intent[expected][1] += 1
            if result.name == expected:
                correct += 1
                per_intent[expected][0] += 1
            else:
                misses.append(f"[误判] {query!r} 期望 {expected} 实际 {result.name} ({result.confidence:.2f})")

        if (i + 1) % 20 == 0:
            print(f"  进度 {i + 1}/{len(cases)}")

    non_oos = len(cases) - oos_total
    accuracy = correct / non_oos * 100 if non_oos else 0
    reject_rate = oos_rejected / oos_total * 100 if oos_total else 0
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    print("\n==== 意图识别评测报告 ====")
    print(f"Accuracy(非 OOS): {correct}/{non_oos} = {accuracy:.1f}%")
    print(f"OOS 拒识率:       {oos_rejected}/{oos_total} = {reject_rate:.1f}%")
    print(f"单条延迟:         均值 {sum(latencies)/len(latencies):.0f}ms | P50 {p50:.0f}ms | P95 {p95:.0f}ms")
    print("\n分意图 Recall:")
    for intent in sorted(per_intent):
        hit, total = per_intent[intent]
        mark = "✓" if hit == total else "✗"
        print(f"  {mark} {intent:20s} {hit}/{total}")
    if misses:
        print("\nBadcase:")
        for m in misses:
            print(f"  {m}")

    print(f"\n结论: Accuracy {accuracy:.1f}% | OOS 拒识 {reject_rate:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
