"""知识检索器：向量召回 + 词法召回（RRF 融合） + CrossEncoder 精排

检索流程（三段式）：
1. 向量召回：Chroma 语义检索 top_k*3 条候选（候选多于最终条数，供融合）
2. 混合召回：对同一语料做 BM25 风格词法打分，与向量排名做 RRF 融合
   —— 解决"语义近但关键词不同"和"关键词命中但语义远"两类漏检
3. 精排：CrossEncoder 重排序（配置 rerank_model 后启用），不可用则退化

性能优化：
- 查询向量复用 embed_query_cached（与意图识别共享一次嵌入）
- 语料全文按 knowledge_version 缓存（版本变更才重新加载）
- 全程同步执行（无 IO 阻塞），单次检索约 100-500ms（CPU）
"""
import time

from langchain_core.documents import Document
from loguru import logger

from app.config.settings import settings
from app.knowledge.embedding import embed_query_cached
from app.knowledge.hybrid import bm25_scores, rrf_fuse
from app.knowledge.vectordb import get_vectorstore

perf_logger = logger.bind(name="perf")


class KnowledgeRetriever:
    def __init__(self, top_k: int = 5, score_threshold: float | None = None,
                 use_hybrid: bool = True, use_rerank: bool = True) -> None:
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.use_hybrid = use_hybrid
        self.use_rerank = use_rerank
        self.vs = get_vectorstore()
        self._corpus: list[tuple[str, str]] | None = None
        self._corpus_version: str = ""
        self._reranker = None
        self._rerank_ready = False
        self._init_reranker()

    def _init_reranker(self) -> None:
        """初始化 CrossEncoder 重排序模型（可选，不可用时降级）"""
        rerank_model = getattr(settings, "rerank_model", None)
        if not rerank_model or not self.use_rerank:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(rerank_model, device="cpu")
            # 预热
            self._reranker.predict([["测试", "测试文档"]])
            self._rerank_ready = True
        except Exception:
            self._rerank_ready = False

    def _load_corpus(self) -> list[tuple[str, str]]:
        """加载语料全文 (content, source_id)，词法召回用，按知识版本缓存

        knowledge_version != "latest" 时按 metadata.version 过滤，
        支撑知识灰度发布（先小流量验证新版本再全量切换）。
        """
        version = getattr(settings, "knowledge_version", "latest")
        if self._corpus is not None and self._corpus_version == version:
            return self._corpus
        try:
            col = self.vs._collection
            where = None if version == "latest" else {"version": version}
            inc = ["documents", "metadatas"]
            data = col.get(include=inc, where=where) if where else col.get(include=inc)
            contents = data.get("documents") or []
            metas = data.get("metadatas") or []
            ids = data.get("ids") or []
            corpus: list[tuple[str, str]] = []
            for i, content in enumerate(contents):
                meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
                sid = meta.get("source_id") or (ids[i] if i < len(ids) else "")
                corpus.append((content, sid))
            self._corpus = corpus
            self._corpus_version = version
        except Exception:
            self._corpus = []
        return self._corpus

    def retrieve(self, query: str) -> list[Document]:
        """同步检索：向量召回 → RRF 融合 → 精排 → Top-K"""
        t_start = time.perf_counter()

        # 1) 向量召回：top_k * 3 条候选
        k = self.top_k * 3 if self._rerank_ready else self.top_k
        t0 = time.perf_counter()
        # 复用请求级查询向量（意图识别已算过则直接命中缓存），避免重复嵌入
        query_vec = embed_query_cached(query)
        docs = self.vs.similarity_search_by_vector(query_vec.tolist(), k=k)
        t_coarse = time.perf_counter() - t0

        if not docs:
            perf_logger.info(f"[retriever] coarse: {t_coarse * 1000:.0f}ms, hits=0, query={query[:50]}")
            return []

        # 2) 词法召回 + RRF 融合（统一文档空间：向量命中 + 语料补全）
        t0 = time.perf_counter()
        corpus = self._load_corpus()
        if corpus and self.use_hybrid:
            seen = {d.page_content for d in docs}
            unified = list(docs) + [
                Document(page_content=c, metadata={"source_id": sid})
                for c, sid in corpus if c not in seen
            ]
            contents = [d.page_content for d in unified]
            content_to_idx = {c: i for i, c in enumerate(contents)}
            vec_rank = {content_to_idx[d.page_content]: r for r, d in enumerate(docs)}
            lex_scores = bm25_scores(query, contents)
            lex_order = sorted(range(len(lex_scores)), key=lambda i: -lex_scores[i])
            lex_rank = {i: r for r, i in enumerate(lex_order) if lex_scores[i] > 0}
            fused_idx = rrf_fuse(vec_rank, lex_rank)[: k * 2]
            docs = [unified[i] for i in fused_idx if i < len(unified)]
        t_hybrid = time.perf_counter() - t0

        # 3) CrossEncoder 精排（可选）
        t_rerank = 0
        if self.use_rerank and self._rerank_ready and self._reranker is not None and len(docs) > self.top_k:
            try:
                t0 = time.perf_counter()
                pairs = [[query, doc.page_content] for doc in docs]
                scores = self._reranker.predict(pairs)
                scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
                docs = [doc for doc, _ in scored[:self.top_k]]
                t_rerank = time.perf_counter() - t0
            except Exception:
                docs = docs[:self.top_k]

        docs = docs[:self.top_k]
        perf_logger.info(
            f"[retriever] coarse={t_coarse * 1000:.0f}ms, hybrid={t_hybrid * 1000:.0f}ms, "
            f"rerank={t_rerank * 1000:.0f}ms, total={(time.perf_counter() - t_start) * 1000:.0f}ms, "
            f"hits={len(docs)}, query={query[:50]}"
        )
        return docs

    async def aretrieve(self, query: str) -> list[Document]:
        """异步检索（供Agent节点调用）"""
        import asyncio

        return await asyncio.to_thread(self.retrieve, query)
