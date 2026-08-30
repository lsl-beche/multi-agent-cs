"""混合检索：向量召回 + 词法（BM25 风格）召回 → RRF 融合

为什么需要混合：
- 纯向量：同义改写/口语化强，但对"精确术语"（龙井、明前）定位弱
- 纯词法：术语精确，但对同义改写弱
- RRF（Reciprocal Rank Fusion）：不依赖分数归一化，只依赖排名，
  融合公式 score = Σ 1/(k + rank)，k 默认 60 抑制长尾

实现要点：
- tokenize：中文轻量分词（单字 + 双字组合），无需外部分词库
- BM25：k1=1.5、b=0.75 的经典参数，适合长短不一的 FAQ 语料
- 生产替换：向量侧换 Milvus、词法侧换 Elasticsearch（fusion 逻辑不变）
"""
import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    """中文轻量分词：单字 + 双字组合（无需外部分词库）

    例子："龙井保存" → [龙,井,保,存,龙井,井保,保存]
    双字组合能捕捉"龙井/明前/普洱"等中文关键词，单字兜底罕见词。
    """
    text = re.sub(r"\s+", "", text or "")
    if not text:
        return []
    chars = list(text)
    tokens = list(chars)
    tokens += [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    return tokens


def _idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    n = max(1, len(corpus_tokens))
    df: Counter = Counter()
    for toks in corpus_tokens:
        df.update(set(toks))
    return {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}


def bm25_scores(query: str, corpus: list[str]) -> list[float]:
    """BM25 风格词法打分（k1=1.5, b=0.75）"""
    if not corpus:
        return []
    corpus_tokens = [tokenize(doc) for doc in corpus]
    idf = _idf(corpus_tokens)
    q_tokens = tokenize(query)
    if not q_tokens:
        return [0.0] * len(corpus)
    avg_len = max(1, sum(len(t) for t in corpus_tokens) / len(corpus_tokens))
    scores = []
    for toks in corpus_tokens:
        tf = Counter(toks)
        dl = len(toks)
        s = 0.0
        for q in set(q_tokens):
            f = tf.get(q, 0)
            if f == 0:
                continue
            s += idf.get(q, 0) * (f * 1.5) / (f + 1.5 * (1 - 0.75 + 0.75 * dl / avg_len))
        scores.append(s)
    return scores


def rrf_fuse(vector_rank: dict[int, int], lexical_rank: dict[int, int], k: int = 60) -> list[int]:
    """RRF 融合：score = Σ 1/(k + rank)"""
    all_ids = set(vector_rank) | set(lexical_rank)
    fused = {}
    for idx in all_ids:
        s = 0.0
        if idx in vector_rank:
            s += 1.0 / (k + vector_rank[idx])
        if idx in lexical_rank:
            s += 1.0 / (k + lexical_rank[idx])
        fused[idx] = s
    return [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])]
