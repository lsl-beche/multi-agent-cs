"""生成"可答辩"的评测集：意图黄金集 + RAG 检索集

为什么要重写生成器（旧版 generate_stage_c_eval.py 的问题）：
1. RAG：query=FAQ 原问句、expected=同一条 FAQ 的答案，而索引就是用同一批 FAQ
   建的 —— 自己检索自己，Hit@5 必然接近 100%，不是真实能力。
   → 本脚本为每条给 gold_id（源文档 source_id），并生成"改写句 / 去关键词句"
     等难题，评测改按文档 id 精确判分，Hit@5 才可信。
2. 意图：标签若用分类器同款关键词规则生成，等于"自证"。
   → 本脚本以人工撰写的种子（按语义定标，独立于分类器关键词）为可信真值，
     FAQ category 与 LLM 只能产出"候选 + needs_review"，需人工复核后才并入黄金集。

用法：
    python scripts/gen_eval.py --no-llm                # 离线：种子+映射+规则，产出候选
    python scripts/gen_eval.py                         # 用 .env 的 LLM 补难题与扩类
    python scripts/gen_eval.py --finalize-intent-review data/eval/intent_review.csv
                                                       # 人工复核后，生成 dialogue_cases.json

输出：
- data/eval/rag_cases.json         RAG 检索集（含 gold_id / variant / answerable）
- data/eval/intent_candidates.json 意图候选集（含 needs_review / split）
- data/eval/intent_review.csv      人工复核清单（填 final_intent 列）
- data/eval/dialogue_cases.json    仅在 --finalize 后写入（人工确认为真值的那部分）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge.pipeline.cleaner import clean_all
from app.knowledge.pipeline.collector import collect_all
from app.knowledge.vectordb import doc_id_for

INTENTS = [
    "query_order", "track_logistics", "return_goods", "exchange_goods",
    "product_consult", "price_inquiry", "promotion_consult", "payment_issue",
    "app_usage", "complaint", "human_service", "chitchat",
]

# category 是"数据侧"信号（与分类器关键词独立），但很粗，一律标 needs_review
CATEGORY_TO_INTENT = {
    "logistics": "track_logistics",
    "order": "query_order",
    "payment": "payment_issue",
    "promotion": "promotion_consult",
    "price": "price_inquiry",
    "product": "product_consult",
    "purchase": "product_consult",
    "aftersale": "product_consult",
}

# 人工撰写种子：按语义定标、覆盖口语/简称/易混边界，作为可直接评测的可信真值。
# 这是"作者提供的标准答案"，仍建议抽查；FAQ/LLM 扩充部分则必须复核。
SEED_INTENTS: dict[str, list[str]] = {
    "query_order": [
        "我的订单现在啥状态了", "帮我看下昨天买的那单发货没", "订单编号怎么查",
        "我下的单子还在待付款吗", "我前几天下的单现在到哪一步了", "查一下我这笔订单详情",
    ],
    "track_logistics": [
        "东西到哪了", "快递单号能给我下吗", "一般几天能到", "我那个包裹现在在哪个城市",
        "物流一直不更新是咋回事", "今天下单明天能收到吗",
    ],
    "return_goods": [
        "这个我想退了", "怎么申请退款啊", "七天无理由怎么弄", "退款多久到账",
        "买回来不喜欢能退吗", "退货的运费谁出",
    ],
    "exchange_goods": [
        "能换一款吗", "尺码不合适想换一件", "发错货了帮我换下", "这个我想换个别的口味",
        "收到的跟我买的不一样，能换吗",
    ],
    "product_consult": [
        "有没有不上火的茶推荐", "龙井怎么泡比较好", "这个茶怎么保存不容易坏",
        "送礼选哪款比较有面子", "生普和熟普有啥区别", "这款是明前茶吗",
    ],
    "price_inquiry": [
        "这个多少钱一斤", "明前龙井什么价位", "会不会太贵了", "有没有性价比高的口粮茶",
        "半斤装的要多少米", "你们家茶叶大概什么价格带",
    ],
    "promotion_consult": [
        "现在有什么优惠活动吗", "有没有满减可以用", "会员积分怎么算的", "能不能给我张优惠券",
        "新用户有福利吗", "双十一有没有折扣",
    ],
    "payment_issue": [
        "我付款失败了是怎么回事", "钱扣了但订单没生成", "能开发票吗怎么开", "支持花呗分期吗",
        "重复扣款了能退一笔吗", "支付方式能不能换一种",
    ],
    "app_usage": [
        "app一打开就闪退", "登录验证码一直收不到", "这个页面打不开", "怎么找不到我的优惠券入口",
        "加载半天刷不出来", "APP提示报错怎么办",
    ],
    "complaint": [
        "我要投诉你们的客服", "这茶质量太差了", "包装破损严重，太不满意了", "再不处理我就去12315了",
        "给我发的货以次充好，我要投诉", "你们这服务我要给差评",
    ],
    "human_service": [
        "我要转人工", "别机器人了给我找个人", "有真人客服吗", "帮我接个人工",
        "我不想跟机器说，转人工", "直接把电话给我，找真人",
    ],
    "chitchat": [
        "你好啊", "谢谢啦", "再见", "你是真人还是机器人", "你叫什么名字", "今天天气不错哈",
    ],
}


# ---------- LLM 辅助（可选，失败即降级，绝不编造） ----------

def _get_llm():
    try:
        from app.core.llm import get_llm_for_task
        return get_llm_for_task("classification", temperature=0.8, streaming=False)
    except Exception:
        return None


def _extract_json(text: str):
    """从模型回复里抠出第一段 JSON（数组或对象）。失败返回 None。"""
    if not text:
        return None
    m = re.search(r"[\[\{].*[\]\}]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _ask_list(llm, prompt: str) -> list[str]:
    if llm is None:
        return []
    try:
        resp = llm.invoke(prompt)
        data = _extract_json(getattr(resp, "content", "") or "")
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


def llm_hard_variants(llm, question: str) -> dict:
    """生成改写句/去关键词句（同义但换措辞），保持语义不变。"""
    if llm is None:
        return {}
    prompt = (
        "你是电商客服检索评测的数据构造助手。请把下面这句用户提问改写成两句'意思相同、但尽量不复用原句关键词'的口语化说法，"
        "用于测试检索的鲁棒性。只输出 JSON 数组，两个字符串元素：[改写句, 去关键词句]。\n"
        f"原句：{question}"
    )
    arr = _ask_list(llm, prompt)
    out = {}
    if len(arr) >= 1 and arr[0].strip():
        out["paraphrase"] = arr[0].strip()
    if len(arr) >= 2 and arr[1].strip():
        out["keyword_gap"] = arr[1].strip()
    return out


def llm_unanswerable(llm, covered: str, n: int) -> list[str]:
    """生成'像本店客服会问到、但知识库其实没有答案'的问题（考拒答，非检索命中）。"""
    if llm is None:
        return []
    prompt = (
        f"下面是某茶叶电商知识库已覆盖的主题：{covered}。\n"
        f"请生成 {n} 个顾客可能问、但上述主题都回答不了的问题（越界/库里没有），"
        "只输出 JSON 数组字符串，不要解释。"
    )
    return _ask_list(llm, prompt)


def llm_intent_utterances(llm, intent: str, desc: str, n: int) -> list[str]:
    if llm is None:
        return []
    prompt = (
        f"客服意图『{intent}』的含义：{desc}。\n"
        f"请生成 {n} 条互不重复、口语化的用户消息，都应属于该意图，"
        "只输出 JSON 数组字符串。"
    )
    return _ask_list(llm, prompt)


# ---------- RAG 集 ----------

def build_rag_cases(pairs: list[dict], target: int, llm, rng: random.Random,
                    hard_ratio: float, unanswerable_ratio: float) -> list[dict]:
    cases: list[dict] = []
    base = pairs[:]
    rng.shuffle(base)
    base = base[: max(1, int(target * (1 - unanswerable_ratio)))]
    n_hard = int(len(base) * hard_ratio)
    hard_targets = set(rng.sample(range(len(base)), min(n_hard, len(base))))
    for i, p in enumerate(base):
        sid = doc_id_for(p["question"], p["answer"])
        cases.append({
            "id": f"rag-{len(cases) + 1:04d}",
            "query": p["question"],
            "gold_id": sid,
            "gold_answer": p["answer"],
            "category": p.get("category", "general"),
            "variant": "original",
            "answerable": True,
            "needs_review": 0,
        })
        if i in hard_targets:
            variants = llm_hard_variants(llm, p["question"]) if llm else {}
            for vname in ("paraphrase", "keyword_gap"):
                q = variants.get(vname)
                if q:
                    cases.append({
                        "id": f"rag-{len(cases) + 1:04d}",
                        "query": q,
                        "gold_id": sid,
                        "gold_answer": p["answer"],
                        "category": p.get("category", "general"),
                        "variant": vname,
                        "answerable": True,
                        "needs_review": 1,  # LLM 改写需抽查语义未漂移
                    })
    # 不可答题（拒答）：gold_id=None
    ua_count = int(target * unanswerable_ratio)
    covered = "、".join(sorted({p.get("category", "general") for p in pairs}))[:800]
    for q in (llm_unanswerable(llm, covered, ua_count) if llm else [])[:ua_count]:
        cases.append({
            "id": f"rag-{len(cases) + 1:04d}",
            "query": q, "gold_id": None, "gold_answer": None,
            "category": "unanswerable", "variant": "unanswerable",
            "answerable": False, "needs_review": 1,
        })
    return cases


# ---------- 意图集 ----------

def _split(mid: str) -> str:
    return "test" if int(hashlib.sha1(mid.encode()).hexdigest(), 16) % 10 < 3 else "dev"


def build_intent_candidates(pairs: list[dict], per_class_min: int, llm,
                            rng: random.Random) -> list[dict]:
    out: list[dict] = []
    seen_msg: set[str] = set()

    def add(msg: str, intent: str, source: str, needs_review: int):
        msg = (msg or "").strip()
        key = re.sub(r"\W+", "", msg)
        if not msg or key in seen_msg or intent not in INTENTS:
            return
        seen_msg.add(key)
        cid = f"int-{len(out) + 1:04d}"
        out.append({
            "id": cid, "message": msg, "candidate_intent": intent,
            "source": source, "needs_review": needs_review, "split": _split(cid),
        })

    # 1) 人工种子：可信真值（needs_review=0）
    for intent in INTENTS:
        for m in SEED_INTENTS.get(intent, []):
            add(m, intent, "seed", 0)

    # 2) FAQ category 映射：候选，必须复核（needs_review=1）
    pool = pairs[:]
    rng.shuffle(pool)
    from app.dialogue.intent import INTENT_DESCRIPTIONS  # 复用意图描述给 LLM
    counts = {i: sum(1 for c in out if c["candidate_intent"] == i) for i in INTENTS}
    for p in pool:
        intent = CATEGORY_TO_INTENT.get(p.get("category", ""), "product_consult")
        if counts.get(intent, 0) >= per_class_min:
            continue
        add(p["question"], intent, "faq_category", 1)
        counts[intent] = counts.get(intent, 0) + 1

    # 3) LLM 扩类补足到 per_class_min（候选，必须复核）
    if llm is not None:
        for intent in INTENTS:
            deficit = per_class_min - counts.get(intent, 0)
            if deficit <= 0:
                continue
            for m in llm_intent_utterances(llm, intent, INTENT_DESCRIPTIONS[intent], deficit + 4):
                if counts.get(intent, 0) >= per_class_min:
                    break
                add(m, intent, "llm", 1)
                counts[intent] = counts.get(intent, 0) + 1

    # 4) 复核 CSV 落地 + 汇总告警
    return out


def summarize_classes(cands: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for c in cands:
        counts[c["candidate_intent"]] = counts.get(c["candidate_intent"], 0) + 1
    return {i: counts.get(i, 0) for i in INTENTS}


def finalize_intent(review_csv: Path, eval_dir: Path) -> int:
    """读人工复核后的 CSV，产出 dialogue_cases.json。

    规则：needs_review=0 的行直接采纳 candidate_intent 为真值；
    needs_review=1 的行仅当 final_intent 非空时采纳（以 final_intent 为准）。
    """
    if not review_csv.exists():
        print(f"未找到复核文件：{review_csv}")
        return 1
    rows = list(csv.DictReader(review_csv.open(encoding="utf-8-sig")))
    cases, dropped = [], 0
    for r in rows:
        needs = str(r.get("needs_review", "1")).strip()
        cand = (r.get("candidate_intent") or "").strip()
        final = (r.get("final_intent") or "").strip()
        intent = final or (cand if needs == "0" else "")
        if intent not in INTENTS:
            dropped += 1
            continue
        mid = r.get("id") or f"int-{len(cases) + 1:04d}"
        cases.append({
            "id": mid, "message": (r.get("message") or "").strip(),
            "expect_intent": intent,
            "split": (r.get("split") or _split(mid)),
        })
    out = eval_dir / "dialogue_cases.json"
    out.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out.name}：{len(cases)} 条真值（丢弃未确认 {dropped} 条）")
    print("下一步：python scripts/eval_dialogue.py --cases data/eval/dialogue_cases.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="生成可答辩的评测集")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--eval-dir", default="data/eval")
    ap.add_argument("--target-rag", type=int, default=500)
    ap.add_argument("--target-intent-per-class", type=int, default=40)
    ap.add_argument("--hard-ratio", type=float, default=0.6)
    ap.add_argument("--unanswerable-ratio", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--finalize-intent-review", default="")
    args = ap.parse_args()

    eval_dir = Path(args.eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    if args.finalize_intent_review:
        return finalize_intent(Path(args.finalize_intent_review), eval_dir)

    rng = random.Random(args.seed)
    pairs = clean_all(collect_all(args.raw_dir))
    if not pairs:
        print("未发现 FAQ 数据（data/raw）")
        return 1
    llm = None if args.no_llm else _get_llm()
    if not args.no_llm and llm is None:
        print("提示：LLM 不可用，将仅产出种子/映射/规则候选（难题与扩类缺失）。可加 --no-llm 静默。")

    rag = build_rag_cases(pairs, args.target_rag, llm, rng, args.hard_ratio, args.unanswerable_ratio)
    cands = build_intent_candidates(pairs, args.target_intent_per_class, llm, rng)

    (eval_dir / "rag_cases.json").write_text(json.dumps(rag, ensure_ascii=False, indent=2), encoding="utf-8")
    (eval_dir / "intent_candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
    with (eval_dir / "intent_review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "message", "candidate_intent", "needs_review", "source", "split", "final_intent"])
        for c in cands:
            w.writerow([c["id"], c["message"], c["candidate_intent"], c["needs_review"], c["source"], c["split"], ""])

    variants = {}
    for c in rag:
        variants[c["variant"]] = variants.get(c["variant"], 0) + 1
    print(json.dumps({
        "rag_cases": len(rag),
        "rag_by_variant": variants,
        "intent_candidates": len(cands),
        "intent_by_class": summarize_classes(cands),
        "llm_used": llm is not None,
    }, ensure_ascii=False, indent=2))
    print("\n下一步：")
    print("  1) 重新入库以生成 source_id：python scripts/ingest_knowledge.py")
    print(f"  2) 复核 {eval_dir / 'intent_review.csv'} 的 final_intent 列")
    print("  3) 定稿意图集：python scripts/gen_eval.py --finalize-intent-review data/eval/intent_review.csv")
    print("  4) 跑评测：python scripts/eval_rag.py --limit 0 && python scripts/eval_dialogue.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
