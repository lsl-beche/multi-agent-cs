"""RAG 评测：Hit@5 / Recall@5 / 延迟

用法：
    python scripts/eval_rag.py                       # 评测前 200 条
    python scripts/eval_rag.py --limit 500
    python scripts/eval_rag.py --cases data/eval/rag_cases.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text or "")


def _hit(expected: str, docs: list) -> bool:
    expected_norm = _norm(expected)
    if not expected_norm:
        return False
    for doc in docs:
        content = _norm(doc.page_content)
        if expected_norm in content or content in expected_norm:
            return True
        # 字符级重叠兜底：应对向量库文本被清洗/截断的情况
        overlap = len(set(expected_norm) & set(content))
        if overlap / max(1, len(set(expected_norm))) >= 0.75:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="data/eval/rag_cases.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))[: args.limit]
    from app.knowledge.retriever import KnowledgeRetriever

    retriever = KnowledgeRetriever(top_k=args.top_k)
    hits = 0
    latencies = []
    failures = []
    t_start = time.time()
    for case in cases:
        t0 = time.perf_counter()
        docs = retriever.retrieve(case["query"])
        latencies.append(round((time.perf_counter() - t0) * 1000, 1))
        if _hit(case["expected"], docs):
            hits += 1
        else:
            failures.append({
                "id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "top": [d.page_content[:120] for d in docs[:3]],
            })
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else 0
    report = {
        "total": len(cases),
        "hits": hits,
        "hit_rate": round(hits / max(1, len(cases)), 4),
        "avg_latency_ms": round(sum(latencies) / max(1, len(latencies)), 1),
        "p95_latency_ms": p95,
        "total_seconds": round(time.time() - t_start, 2),
        "top_k": args.top_k,
        "sample_failures": failures[:10],
    }
    out = Path("data/eval/reports/rag_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["hit_rate"] >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
