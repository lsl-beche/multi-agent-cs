"""生成阶段 C 评测数据：RAG 命中集 + 客服黄金对话集

数据来源：data/raw/*.json（500 条茶叶客服 FAQ）。
输出：
- data/eval/rag_cases.json：RAG Hit@5 / Recall@5 评测用例
- data/eval/dialogue_cases.json：保留原黄金集并扩展到 ≥200 条意图评测用例
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _faq_rows(raw_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(raw_dir.glob("*.json")):
        try:
            rows.extend(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return [r for r in rows if r.get("question") and r.get("answer")]


def _intent_for(question: str, category: str) -> str:
    q = question or ""
    if any(k in q for k in ("投诉", "太差", "差劲", "生气", "不满意", "举报")):
        return "complaint"
    if any(k in q for k in ("人工", "真人", "找客服", "转人工")):
        return "human_service"
    if any(k in q for k in ("退货", "退款", "退钱", "七天无理由")):
        return "return_goods"
    if any(k in q for k in ("换货", "换一件", "换个", "更换", "发错")):
        return "exchange_goods"
    if any(k in q for k in ("收到货", "到手", "包装", "破损", "损坏", "漏", "少发", "坏了")):
        return "return_goods"
    if any(k in q for k in ("快递", "物流", "发货", "包裹", "签收", "揽收")):
        return "track_logistics"
    if any(k in q for k in ("订单", "下单", "确认收货", "取消订", "地址")):
        return "query_order"
    if any(k in q for k in ("支付", "扣款", "付款", "发票", "税")):
        return "payment_issue"
    if any(k in q for k in ("优惠", "优惠券", "促销", "活动", "折扣", "积分", "会员")):
        return "promotion_consult"
    if any(k in q for k in ("多少钱", "价格", "一斤", "贵")):
        return "price_inquiry"
    if any(k in q for k in ("页面", "登录", "验证码", "打不开", "加载")):
        return "app_usage"
    if category in ("logistics",) and any(k in q for k in ("物流", "快递", "发货", "包裹")):
        return "track_logistics"
    if category in ("order",) and any(k in q for k in ("订单", "下单", "地址", "取消", "确认收货")):
        return "query_order"
    if category in ("payment",):
        return "payment_issue"
    if category in ("promotion",):
        return "promotion_consult"
    if category in ("aftersale",):
        return "product_consult"
    return "product_consult"


def build_rag_cases(rows: list[dict]) -> list[dict]:
    return [
        {
            "id": f"rag-{idx:04d}",
            "query": r["question"],
            "expected": r["answer"],
            "category": r.get("category", "general"),
        }
        for idx, r in enumerate(rows, start=1)
    ]


def build_dialogue_cases(rows: list[dict], existing_path: Path, target: int = 240) -> list[dict]:
    existing = []
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    # 每次重新生成 stage3 用例，避免旧的映射影响新评测集
    existing = [case for case in existing if not str(case.get("id", "")).startswith("stage3-")]
    seen = {case.get("message", "") for case in existing}
    result = list(existing)
    idx = len(result) + 1
    for row in rows:
        if len(result) >= target:
            break
        message = row["question"]
        if message in seen:
            continue
        seen.add(message)
        result.append({
            "id": f"stage3-{idx:04d}",
            "message": message,
            "expect_intent": _intent_for(message, row.get("category", "")),
            "category": row.get("category", "general"),
        })
        idx += 1
    # 保底补充：保证常见意图都有覆盖
    if len(result) < target:
        extras = [
            ("投诉你们的快递太慢了", "complaint"),
            ("我要找真人客服", "human_service"),
            ("谢谢你的帮助", "chitchat"),
            ("这款茶多少钱一斤", "price_inquiry"),
        ]
        for message, intent in extras:
            if len(result) >= target:
                break
            if message not in seen:
                result.append({
                    "id": f"stage3-{idx:04d}", "message": message,
                    "expect_intent": intent, "category": "补充",
                })
                idx += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="生成阶段C评测数据")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--eval-dir", default="data/eval")
    parser.add_argument("--target", type=int, default=240)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    eval_dir = Path(args.eval_dir)
    rows = _faq_rows(raw_dir)
    if not rows:
        print("未发现 FAQ 数据")
        return 1

    eval_dir.mkdir(parents=True, exist_ok=True)
    rag_cases = build_rag_cases(rows)
    dialogue_cases = build_dialogue_cases(rows, eval_dir / "dialogue_cases.json", args.target)
    (eval_dir / "rag_cases.json").write_text(
        json.dumps(rag_cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (eval_dir / "dialogue_cases.json").write_text(
        json.dumps(dialogue_cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (eval_dir / "reports").mkdir(parents=True, exist_ok=True)
    print(json.dumps({
        "faq_rows": len(rows),
        "rag_cases": len(rag_cases),
        "dialogue_cases": len(dialogue_cases),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
