"""RAG 评测：按 gold doc id 精确判分 + 组件消融 + 置信区间

与旧版的关键区别（旧版为何不可信）：
- 旧版判命中用"文本子串/75%字符重叠"近似，且 query 就是 FAQ 原句、检索的又是
  同一批 FAQ → 近乎必中，Hit@5=100% 无意义。
- 新版按 retriever 返回文档的 source_id 与用例 gold_id 精确匹配；
  用例含"改写句/去关键词句/不可答题"，并按 原句 vs 难题 分桶报告；
  同一冻结集上跑三档配置（仅向量 / +BM25融合 / +重排）做消融，
  给出真实"逐级提升"，并对命中率给 Wilson 95% 置信区间。

用法：
    python scripts/eval_rag.py                     # 全量、三档消融
    python scripts/eval_rag.py --limit 200
    python scripts/eval_rag.py --configs hybrid_rerank
    python scripts/eval_rag.py --top-k 5 --threshold 0.7

依赖：data/eval/rag_cases.json 含 gold_id；向量库需含 source_id
      （先跑 python scripts/ingest_knowledge.py 重建）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge.metrics import (
    hit_at_k, mrr_at_k, ndcg_at_k, recall_at_k, wilson_interval,
)
from app.knowledge.retriever import KnowledgeRetriever

CONFIGS = {
    "vector_only": {"use_hybrid": False, "use_rerank": False},
    "hybrid": {"use_hybrid": True, "use_rerank": False},
    "hybrid_rerank": {"use_hybrid": True, "use_rerank": True},
}
HEADLINE = "hybrid_rerank"


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    ordered = sorted(xs)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 1)


def _doc_ids(docs: list) -> tuple[list[str], bool]:
    ids, saw_sid = [], False
    for d in docs:
        sid = (getattr(d, "metadata", None) or {}).get("source_id")
        if sid:
            saw_sid = True
            ids.append(sid)
        else:
            ids.append("")  # 保持位次，未入库 id 视为不命中
    return ids, saw_sid


def evaluate(cases: list[dict], top_k: int, configs: list[str]) -> dict:
    answerable = [c for c in cases if c.get("answerable", True) and c.get("gold_id")]
    n_missing = sum(1 for c in cases if c.get("answerable", True) and not c.get("gold_id"))
    n_unanswerable = sum(1 for c in cases if not c.get("answerable", True))

    result: dict[str, dict] = {}
    saw_source_id = False
    report_cfg = HEADLINE if HEADLINE in configs else configs[0]
    per_config_retrievers = {
        name: KnowledgeRetriever(top_k=top_k, **CONFIGS[name]) for name in configs
    }
    variant_records: list[tuple[str, float]] = []  # (variant, hit) —— 仅 report_cfg

    for name in configs:
        retriever = per_config_retrievers[name]
        hits = recalls = ndcgs = 0.0
        rr_sum = 0.0
        hit_count = 0
        latencies: list[float] = []
        failures: list[dict] = []
        for case in answerable:
            gold = {case["gold_id"]}
            t0 = time.perf_counter()
            docs = retriever.retrieve(case["query"])
            latencies.append(round((time.perf_counter() - t0) * 1000, 1))
            ids, saw = _doc_ids(docs)
            saw_source_id = saw_source_id or saw
            h = hit_at_k(ids, gold, top_k)
            hits += h
            hit_count += int(h)
            recalls += recall_at_k(ids, gold, top_k)
            rr_sum += mrr_at_k(ids, gold, top_k)
            ndcgs += ndcg_at_k(ids, gold, top_k)
            if name == report_cfg:
                variant_records.append((case.get("variant", "unknown"), h))
            if h == 0 and len(failures) < 10:
                failures.append({
                    "id": case.get("id"), "variant": case.get("variant"),
                    "query": case.get("query"),
                    "gold_id": case.get("gold_id"), "top_ids": ids[:top_k],
                })
        n = max(1, len(answerable))
        _, lo, hi = wilson_interval(hit_count, len(answerable))
        result[name] = {
            "rerank_enabled": getattr(retriever, "_rerank_ready", False),
            f"hit@{top_k}": round(hits / n, 4),
            f"recall@{top_k}": round(recalls / n, 4),
            f"mrr@{top_k}": round(rr_sum / n, 4),
            f"ndcg@{top_k}": round(ndcgs / n, 4),
            "hit_ci95": [round(lo, 4), round(hi, 4)],
            "avg_latency_ms": round(sum(latencies) / max(1, len(latencies)), 1),
            "p95_latency_ms": _p95(latencies),
            "sample_failures": failures,
        }

    # 按难度分桶（复用 report_cfg 的结果，不再重复检索）
    by_variant: dict[str, dict] = {}
    for variant, h in variant_records:
        stat = by_variant.setdefault(variant, {"n": 0, "hits": 0})
        stat["n"] += 1
        stat["hits"] += int(h)
    for stat in by_variant.values():
        stat[f"hit@{top_k}"] = round(stat["hits"] / max(1, stat["n"]), 4)

    return {
        "n_total_cases": len(cases),
        "n_answerable": len(answerable),
        "n_unanswerable_excluded": n_unanswerable,
        "n_missing_gold_id": n_missing,
        "kb_has_source_id": saw_source_id,
        "configs": result,
        "by_variant": by_variant,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG 严格评测（id 判分 + 消融 + CI）")
    ap.add_argument("--cases", default="data/eval/rag_cases.json")
    ap.add_argument("--limit", type=int, default=0, help="0=全量")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--configs", default=",".join(CONFIGS.keys()),
                    help="逗号分隔：vector_only,hybrid,hybrid_rerank")
    ap.add_argument("--threshold", type=float, default=0.7, help="headline hit@k 质量门禁")
    args = ap.parse_args()

    configs = [c.strip() for c in args.configs.split(",") if c.strip() in CONFIGS]
    if not configs:
        print("无有效 --configs")
        return 1

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    report = evaluate(cases, args.top_k, configs)
    out = Path("data/eval/reports/rag_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not report["kb_has_source_id"]:
        print("\n[警告] 检索结果未见 source_id —— 请先运行 "
              "`python scripts/ingest_knowledge.py` 重建知识库，否则 id 判分全部落空。")
    if report["n_missing_gold_id"]:
        print(f"[警告] {report['n_missing_gold_id']} 条用例缺 gold_id 被跳过，"
              "请用 `python scripts/gen_eval.py` 重新生成评测集。")

    head_cfg = report["configs"].get(HEADLINE) or report["configs"].get(configs[0])
    gate = head_cfg and head_cfg.get(f"hit@{args.top_k}", 0) >= args.threshold
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
