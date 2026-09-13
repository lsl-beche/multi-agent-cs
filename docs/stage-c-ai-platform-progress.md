# 阶段 C · AI 平台化实跑进度

> 对应：`docs/enterprise-10m-plan.md`「阶段三：AI 平台化」
> 状态：本地可运行版本已完成，生产依赖（GPU/Milvus/外部 API）保留就绪接口。

## 已完成

### Agent 运行时平台

- 结构化运行 Trace（Redis + 进程内降级）：
  - `app/agents/trace.py`
  - 记录节点、工具、LLM、状态、耗时、意图、最终回答；
  - 管理接口：`GET /api/admin/agents/traces`、`GET /api/admin/agents/traces/{run_id}`；
  - Trace 默认保留 7 天，最大 5000 条。
- 工具市场：
  - `app/tools/registry.py` 增加分类、只读/写权限、风险、启用状态；
  - `PUT /api/admin/agents/tools/{name}/state` 支持启用/停用；
  - `BaseAgent` 执行工具前检查启用状态并写入 Trace。
- 模型分层路由：
  - 小模型：意图、摘要、偏好、情感；
  - 大模型：知识、订单、售后、合规、促销等复杂任务；
  - 配置：`LLM_FAST_MODEL`、`LLM_LARGE_MODEL`、`LLM_FAST_BASE_URL`、`LLM_LARGE_BASE_URL`；
  - 指标：`csagent_model_routed_total{task,tier}`。
- 管理前端：
  - `web/admin/src/views/agents/AgentPlatformView.vue`
  - `/agents` 页面：运行统计、工具市场、Trace 列表与详情。

### RAG 与知识治理

- FAQ 语料：500 条，覆盖茶叶品种、冲泡、存储、购买、售后、物流、订单、支付、促销等。
- 混合检索：向量召回 + BM25 词法 + RRF 融合，可选 CrossEncoder 精排。
- 知识版本：`ingest_knowledge.py --version` + `KnowledgeUpdater.upsert(version=...)`。
- Webhook 支持 `knowledge.upsert`、商品上下架热更新。

### 评测体系

- 客服黄金语料：240 条（原有 40 条保留 + Stage C 扩展 200 条）。
- RAG 评测集：500 条 FAQ 命中用例，默认评测 200 条。
- 脚本：
  - `scripts/generate_stage_c_eval.py`
  - `scripts/eval_rag.py`
  - `scripts/eval_dialogue.py`
  - `scripts/eval_recommend.py`

## 实跑结果

| 项目 | 结果 |
|---|---|
| RAG Hit@5 | 200/200，100% |
| RAG 平均检索延迟 | 286ms |
| RAG P95 检索延迟 | 323ms |
| 客服意图评测 | 240 条，87.9%（本地 BGE 分类器；目标 90% 需微调标注模型） |
| 推荐离线 eval | ItemCF + UserCF + 偏好 + 热销，平均 18.5ms |
| Admin 前端构建 | `vue-tsc` + Vite build 通过 |
| 后端测试 | 25 passed |
| 真实客服对话 | 知识/物流意图正确，Agent Trace 生成并可回放 |

## 待生产化接入

- vLLM/GPU 推理集群：`deploy/k8s/vllm.yaml` 已就绪，需真实 GPU 节点；
- Milvus：代码已预留 `VECTOR_DB_TYPE=milvus` 开关，需安装 `pymilvus` 并部署；
- 意图/情感模型微调：当前为 BGE 分类 + 关键词规则，目标 ≥90% 需标注数据微调；
- 分布式记忆容量治理：当前 Redis + Chroma，按用户过滤且支持遗忘权，亿级需分片；
- 客服质检/在线 A/B/反馈回流：已有质量脚本，需上线后接入真实反馈流。
