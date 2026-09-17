# 评测方法学（RAG + 意图）与如何复现

> 目的：让简历/答辩里出现的每个数字都能**当场跑出来、经得起追问**。
> 核心原则：不自证、不松判、报样本量与置信区间、难题与易题分开看。

## 1. 旧评测为什么不可信

| 维度 | 旧做法 | 问题 |
|---|---|---|
| RAG 用例 | query=FAQ 原问句，expected=同一条 FAQ 答案，索引也由这批 FAQ 建 | 自己检索自己，Hit@5 必然≈100%，非真实能力 |
| RAG 判分 | 文本子串双向包含 或 **字符集重叠≥75%** 即算命中 | 松判导致假命中，指标虚高 |
| RAG 样本量 | 报告默认 `--limit 200`，但对外写"420/500" | 口径对不上，任何面试官一算即穿帮 |
| 意图标签 | 由关键词启发式 `_intent_for` 生成，分类器又跑同款关键词强触发 | 生成器与被判对象同源，**循环自证** |
| 意图分布 | 兜底全落 `product_consult` | 类别失衡，整体准确率被大类抬高、掩盖小类 |
| 报告口径 | 只有单一 accuracy，无误差、无逐类 | 无法判断"88%"到底稳不稳 |

**一个算术自检**：命中率=命中数/总数。96.5% 要求总数是 200 的倍数，420 和 500 都凑不出
96.5%（420→96.4% 或 96.7%；500→96.4% 或 96.6%）。所以"420 条 + 96.5%"在数学上不自洽。

## 2. 新评测设计

### RAG（`scripts/eval_rag.py` + `app/knowledge/metrics.py`）
- **精确判分**：检索返回的每篇文档带稳定 `source_id`（内容寻址，见 `vectordb.doc_id_for`），
  用例记 `gold_id`，命中=召回列表里出现 gold_id。不再用文本重叠近似。
- **难题化**：`gen_eval.py` 为部分用例用 LLM 生成 `paraphrase`（同义改写）与
  `keyword_gap`（去关键词）变体，并注入约 10% `unanswerable`（库里没有答案，考拒答）。
  避免"自检索自"的饱和。
- **消融**：同一冻结集上跑三档 —— `vector_only` → `hybrid`(+BM25/RRF) →
  `hybrid_rerank`(+CrossEncoder)。得到真实的"逐级提升"。若未配置 `RERANK_MODEL`，
  报告会显式 `rerank_enabled=false`，此时**不得**在简历里写"重排"。
- **分桶 + 区间**：按 `variant` 分别报 Hit@5；headline 给 Wilson 95% 置信区间。

### 意图（`scripts/eval_dialogue.py`）
- **可信真值**：以人工撰写种子（`gen_eval.SEED_INTENTS`，按语义定标、独立于分类器关键词）
  为核心真值；FAQ category 映射与 LLM 扩充只作**候选**，一律 `needs_review=1`，
  需人工在 `intent_review.csv` 填 `final_intent` 后 `--finalize` 才进黄金集。
- **多维指标**：top-1 accuracy + Wilson CI、macro-F1、每类 precision/recall/f1/support、混淆矩阵。
- **冻结 test**：`--split test` 只在未参与调阈值/关键词的子集上报数（对外引用口径）。

## 3. 多少条合适（含依据）

比例的 95% CI 半宽 ≈ 1.96·√(p(1−p)/n)，取 p≈0.88：

| n | ±pp | 说明 |
|---|---|---|
| 240 | 4.1 | 偏宽，"88%"实为 84–92% |
| 400 | 3.2 | 可接受 |
| 500 | 2.8 | 简历甜点区 |

真正的约束是**逐类覆盖**：12 类要报 macro-F1/每类 P-R，每类经验上 ≥30~40 才稳。
12×40=480 → **意图集定 500、每类≥40**，并冻结约 30% 作 test。
**RAG 集定 500**，其中原句:难题:拒答 ≈ 3:6:1；可信度来自"难题 + 精确判分 + 消融"，不是堆条数。

## 4. 复现步骤（产出可引用的真数字）

> Windows 控制台若中文乱码，先 `chcp 65001` 或用 `set PYTHONUTF8=1`。

```bash
# 0) 生成评测集（含 LLM 难题/扩类）。需 LLM 服务在线（.env: LLM_PROVIDER=local 或云端 key）
python scripts/gen_eval.py                # 去掉 --no-llm 才会产改写句并把小类补到每类≥40

# 1) 重新入库，让每篇文档带上 source_id（严格判分的前提）
python scripts/ingest_knowledge.py

# 2) 人工复核意图候选：编辑 data/eval/intent_review.csv 的 final_intent 列
#    （needs_review=0 的种子默认可信；=1 的候选必须确认后才计入真值）
python scripts/gen_eval.py --finalize-intent-review data/eval/intent_review.csv

# 3) 跑评测
python scripts/eval_rag.py --limit 0            # 全量、三档消融、CI
python scripts/eval_dialogue.py --split test    # 冻结 test 上报
```

产物：`data/eval/reports/rag_report.json`、`dialogue_report.json`。

## 5. 简历怎么写（用报告里的真值替换尖括号）

> **RAG 检索**：BGE+BM25 双路召回、RRF、[仅当 rerank_enabled=true 才写：CrossEncoder 重排]；
> 在 <N> 条自建评测集（含 <M> 条改写/去关键词难题）上按文档 id 精确判分，
> Hit@5 由向量单路 <A>% 提升至 <B>%（+BM25 后 <C>%，+重排后 <D>%），
> top_k=5、平均 <X>ms、P95 <Y>ms（500-doc、CPU），95%CI ±<E>pp。
>
> **意图识别**：<T> 条人工复核黄金集（12 类、每类≥<P>）在冻结 test 上 top-1 <F>%
> （95%CI ±<G>pp）、macro-F1 <H>；分层路由把 <I>% 高频意图挡在小模型侧。

规则：**每个数字都能指向 `reports/*.json` 里的字段**。填不出来源的，删掉或改定性表述。
