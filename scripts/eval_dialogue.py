"""对话评测：黄金集回归（意图识别快速模式 + 可选全链路模式）

用法：
    python scripts/eval_dialogue.py                 # 意图识别回归（快）
    python scripts/eval_dialogue.py --full 5        # 前5条走完整Agent工作流
    python scripts/eval_dialogue.py --threshold 0.7
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_cases(path: str = "data/eval/dialogue_cases.json") -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def eval_intent(cases: list[dict]) -> dict:
    from app.dialogue.intent import IntentClassifier

    clf = IntentClassifier()
    ok = 0
    failures = []
    t0 = time.time()
    for case in cases:
        result = clf.classify(case["message"])
        if result.name == case["expect_intent"]:
            ok += 1
        else:
            failures.append({
                "id": case["id"],
                "message": case["message"],
                "expect": case["expect_intent"],
                "got": result.name,
                "conf": round(result.confidence, 3),
            })
    return {
        "mode": "intent",
        "total": len(cases),
        "passed": ok,
        "accuracy": round(ok / len(cases), 4) if cases else 0,
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
            failures.append({"id": case["id"], "message": case["message"], "expect": case["expect_intent"], "got": got})
    return {"mode": "full", "total": min(limit, len(cases)), "passed": ok,
            "accuracy": round(ok / min(limit, len(cases)), 4) if cases else 0, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", type=int, default=0, help="前N条走完整工作流")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--cases", default="data/eval/dialogue_cases.json")
    parser.add_argument("--output", default="data/eval/reports/dialogue_report.json")
    args = parser.parse_args()

    cases = load_cases(args.cases)
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
    return 0 if acc >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
