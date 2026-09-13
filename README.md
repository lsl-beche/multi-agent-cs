# CSagent — 电商店铺智能客服 Agent 平台

基于**多Agent协同架构（Supervisor编排模式）**的电商智能客服系统，可自主推理、调用业务接口、维护多轮上下文，目标替代人工处理 70%-80% 重复性咨询。

> 完整技术方案见 [流程设计.md](./流程设计.md)，目录结构说明见其中 3.4 节。

## 技术栈

| 层级 | 方案 |
|------|------|
| Agent编排 | LangChain / LangGraph |
| LLM | DeepSeek / Qwen（OpenAI兼容接口） |
| 向量数据库 | Chroma（开发）/ Milvus（生产） |
| Embedding | BGE-large-zh |
| 后端 | FastAPI + WebSocket |
| 存储 | PostgreSQL（业务）/ Redis（缓存、会话） |
| 部署 | Docker + Kubernetes |

## 快速开始

```bash
# 1. 创建并激活虚拟环境（Python >= 3.10）
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell / CMD
# source .venv/bin/activate  # macOS / Linux

# 2. 安装依赖（首次下载约3GB，含torch/chromadb/llama-cpp-python等）
pip install -r requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 3. 配置环境变量（.env 已包含PostgreSQL连接串，无需额外修改）
# 默认即为本地LLM模式，无需API Key

# 4. 初始化PostgreSQL数据库（首次运行，自动建库建表）
python scripts/init_db.py

# 5. 启动本地LLM服务（新开一个终端，保持运行）
.venv\Scripts\activate      # 新终端重新激活
python scripts/start_local_llm.py

# 6. 知识库入库（先往 data/raw/ 放入FAQ语料）
python scripts/ingest_knowledge.py

# 7. 启动服务
uvicorn app.main:app --reload
```

## 本地LLM（免API Key）

项目默认使用本地部署的小型LLM，**无需任何云端API Key**：

| 项 | 说明 |
|----|------|
| 模型 | Qwen2.5-3B-Instruct（GGUF Q4_K_M量化，约1.9GB） |
| 位置 | `models/qwen2.5-3b-instruct-q4_k_m.gguf` |
| 推理引擎 | llama.cpp（CPU即可运行，约10+ tokens/s） |
| 接口 | OpenAI兼容 `http://127.0.0.1:8001/v1` |

```bash
# 启动/停止本地LLM
python scripts/start_local_llm.py            # 默认端口8001，上下文4096
python scripts/start_local_llm.py --port 8002 --ctx 8192   # 自定义
```

切换云端API：`.env` 中把 `LLM_PROVIDER` 改为 `deepseek` 并填 `LLM_API_KEY` 即可，`app/core/llm.py` 自动路由。

> Windows安装推理依赖请用预编译wheel源（避免源码编译）：
> `pip install "llama-cpp-python[server]" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`

启动后访问：
- API文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`
- 对话接口：`POST /api/chat` 或 `WS /api/chat/ws`

## 本地一键部署（含PostgreSQL/Redis）

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## 目录结构速览

```
app/
├── api/        # API Gateway层：中间件（鉴权/限流/日志）+ 路由
├── agents/     # Agent核心层：Supervisor编排 + 4个专业子Agent + LangGraph状态图
├── tools/      # 工具注册中心：商品/订单/物流/政策/工单
├── dialogue/   # 对话管理：意图识别、槽位填充、多轮记忆、人工转接
├── services/   # 电商微服务对接：商品/订单/支付/物流
├── knowledge/  # 知识库：采集清洗 -> 分块 -> 向量化 -> 检索 -> 热更新
├── core/       # 基础设施：LLM客户端、Redis、PostgreSQL、安全
└── models/     # Pydantic模型 + SQLAlchemy表结构
```

## 工程规范

- 开发环境搭建：[docs/developer-setup.md](./docs/developer-setup.md)
- 环境变量规范：[docs/env-spec.md](./docs/env-spec.md)
- 分支保护规范：[docs/branch-protection.md](./docs/branch-protection.md)
- 架构决策记录：[docs/adr/](./docs/adr/)
- 企业级路线图：[docs/enterprise-l2-roadmap.md](./docs/enterprise-l2-roadmap.md)
- AI 平台化进度：[docs/stage-c-ai-platform-progress.md](./docs/stage-c-ai-platform-progress.md)
- 安全/开放/生产化进度：[docs/stage-de-production-progress.md](./docs/stage-de-production-progress.md)
- 提交流程见 [CONTRIBUTING.md](./CONTRIBUTING.md)

## 测试

```bash
pytest tests/ -v
```
