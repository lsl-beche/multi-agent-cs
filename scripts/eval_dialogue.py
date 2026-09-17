"""意图评测：黄金集回归（top-1 准确率 + macro-F1 + 每类 P/R + 置信区间）

与旧版区别：
- 旧版只报单一 accuracy，类别不均衡时会被大类拉高、掩盖小类短板；
- 新版同时报 macro-F1（对每类等权，暴露"chitchat/human_service"等小类）、
  每类 precision/recall、混淆矩阵（定位易混对），并给 top-1 准确率的
  Wilson 95% 置信区间；支持 dev/test 划分，最终只在冻结 test 上报数。

用法：
    python scripts/eval_dialogue.py                 # 全量意图回归
    python scripts/eval_dialogue.py --split test    # 只在 test 子集上报（推荐对外引用）
    python scripts/eval_dialogue.py --full 5        # 前5条走完整 Agent 工作流
    python scripts/eval_dialogue.py --threshold 0.8
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge.metrics import (
    accuracy, confusion_matrix, macro_f1, per_class_metrics, wilson_interval,
)


def load_cases(path: str, split: str, limit: int) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if split and split != "all":
        cases = [c for c in cases if (c.get("split") or "dev") == split]
    if limit and limit > 0:
        cases = cases[:limit]
    return cases


def eval_intent(cases: list[dict]) -> dict:
    from app.dialogue.intent import IntentClassifier

    clf = IntentClassifier()
    y_true: list[str] = []
    y_pred: list[str] = []
    failures: list[dict] = []
    t0 = time.time()
    for case in cases:
        result = clf.classify(case["message"])
        y_true.append(case["expect_intent"])
        y_pred.append(result.name)
        if result.name != case["expect_intent"]:
            failures.append({
                "id": case["id"], "message": case["message"],
                "expect": case["expect_intent"], "got": result.name,
                "conf": round(result.confidence, 3),
            })
    n = len(cases)
    correct = accuracy(y_true, y_pred)
    point, lo, hi = wilson_interval(correct, n)
    per_class = per_class_metrics(y_true, y_pred)
    return {
        "mode": "intent",
        "total": n,
        "passed": correct,
        "accuracy": round(point, 4),
        "accuracy_ci95": [round(lo, 4), round(hi, 4)],
        "macro_f1": macro_f1(per_class),
        "per_class": per_class,
        "confusion": confusion_matrix(y_true, y_pred),
        "seconds": round(time.time() - t0, 2),
        "failures": failures,
    }


def eval_full(cases: list[dict], limit: int) -> dict:
    import asyncio

    from langchain_core.messages import HumanMessage

    from app.agents.graphs.workflow import build_workflow

    workflow = build_workflow()

    async def _run(case: dict) -> tuple[bool, str]:
        result = await workflow.ainvoke({
            "messages": [HumanMessage(content=case["message"])],
            "session_id": f"eval-{case['id']}",
            "user_id": "eval",
            "slots": {},
        })
        return result.get("intent") == case["expect_intent"], result.get("intent", "")

    ok = 0
    failures = []
    for case in cases[:limit]:
        try:
            passed, got = asyncio.run(_run(case))
        except Exception as e:
            passed, got = False, f"ERROR:{type(e).__name__}"
        if passed:
            ok += 1
        else:
            failures.append({"id": case["id"], "message": case["message"],
                             "expect": case["expect_intent"], "got": got})
    return {"mode": "full", "total": min(limit, len(cases)), "passed": ok,
            "accuracy": round(ok / min(limit, len(cases)), 4) if cases else 0,
            "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser(description="意图评测（含 macro-F1 / 每类 P/R / CI）")
    ap.add_argument("--cases", default="data/eval/dialogue_cases.json")
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"],
                    help="对外引用建议 test（冻结集，未参与调阈值/关键词）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--full", type=int, default=0, help="前N条走完整工作流")
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--output", default="data/eval/reports/dialogue_report.json")
    args = ap.parse_args()

    cases = load_cases(args.cases, args.split, args.limit)
    if not cases:
        print(f"无评测用例（cases={args.cases}, split={args.split}）。"
              "请先 `python scripts/gen_eval.py` 生成并 finalize 意图集。")
        return 1

    report = eval_intent(cases)
    if args.full > 0:
        full = eval_full(cases, args.full)
        report["full_flow"] = full
        report["accuracy"] = full["accuracy"]
        report["passed"] = full["passed"]
        report["total"] = full["total"]

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    acc = report.get("full_flow", {}).get("accuracy", report["accuracy"])
    if acc < args.threshold:
        print(f"\n[提示] accuracy {acc:.3f} 低于门禁 {args.threshold}。"
              "查看 per_class / confusion 定位短板类，而非只盯整体数字。")
    return 0 if acc >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
