"""评测指标：RAG 检索质量 + 分类质量 + 比例置信区间

纯 Python 实现，无第三方依赖，供 scripts/eval_*.py 复用。
设计目标：让报出的每个数字都带样本量和统计误差，可当场复现。

检索侧：hit@k / recall@k / mrr@k / ndcg@k，均基于"文档 id 精确匹配"，
不再用文本重叠近似判分（近似匹配会让自建集近乎必中，指标失真）。
分类侧：macro-F1、每类 precision/recall/f1、混淆矩阵。
统计侧：wilson_interval 给出比例的 95% 置信区间半宽。
"""
from __future__ import annotations

import math


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


# ---------- 置信区间 ----------

def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """二项比例的 Wilson 95% 置信区间。

    返回 (point, lo, hi)，均为 0~1 的比例。n=0 时返回 (0, 0, 0)。
    相比正态近似，Wilson 在 p 接近 0/1、样本较小（如每类 40 条）时更稳健，
    适合给"命中率/准确率"配一个诚实的误差范围。
    """
    if n <= 0:
        return 0.0, 0.0, 0.0
    phat = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(_safe_div(phat * (1 - phat), n) + z2 / (4 * n * n))
    return phat, max(0.0, center - half), min(1.0, center + half)


def margin_of_error_95(successes: int, n: int) -> float:
    """报告口径：95% 置信区间的半宽（百分点小数，如 0.028 表示 ±2.8pp）。"""
    _, lo, hi = wilson_interval(successes, n)
    return (hi - lo) / 2


# ---------- 检索质量（按 id） ----------

def hit_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int) -> float:
    """top-k 内是否命中任一金标文档：命中=1，否则=0。"""
    if not gold_ids:
        return 0.0
    return 1.0 if any(rid in gold_ids for rid in retrieved_ids[:k]) else 0.0


def recall_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int) -> float:
    """top-k 覆盖了多少比例的金标文档（单金标时等价于 hit）。"""
    if not gold_ids:
        return 0.0
    hits = len(gold_ids & set(retrieved_ids[:k]))
    return _safe_div(hits, len(gold_ids))


def mrr_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int) -> float:
    """首个命中的排名倒数；未命中=0。反映"正确答案排多前"。"""
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in gold_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], gold_ids: set[str], k: int) -> float:
    """二元相关性 nDCG@k：命中位置越靠前得分越高，按理想 DCG 归一。"""
    if not gold_ids:
        return 0.0
    dcg = 0.0
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in gold_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(gold_ids), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return _safe_div(dcg, idcg)


# ---------- 分类质量 ----------

def per_class_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, float]]:
    """逐类 precision / recall / f1 / support。

    类别集合取 gold 中出现的标签（评测集应覆盖全部意图），
    未在任何预测中命中的类 recall=0，避免"消失的类"被忽略。
    """
    labels = sorted(set(y_true))
    out: dict[str, dict[str, float]] = {}
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        support = sum(1 for t in y_true if t == lab)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        out[lab] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
    return out


def macro_f1(per_class: dict[str, dict[str, float]]) -> float:
    """各类 F1 的算术平均（不受类别频次影响，暴露小类短板）。"""
    if not per_class:
        return 0.0
    return round(sum(m["f1"] for m in per_class.values()) / len(per_class), 4)


def accuracy(y_true: list[str], y_pred: list[str]) -> int:
    """正确的样本数（配合 wilson_interval 得到点估计与区间）。"""
    return sum(1 for t, p in zip(y_true, y_pred) if t == p)


def confusion_matrix(y_true: list[str], y_pred: list[str]) -> dict[str, dict[str, int]]:
    """confusion[真实类][预测类] = 计数，用于定位易混对做定向补强。"""
    mat: dict[str, dict[str, int]] = {}
    for t, p in zip(y_true, y_pred):
        mat.setdefault(t, {})
        mat[t][p] = mat[t].get(p, 0) + 1
    return mat
