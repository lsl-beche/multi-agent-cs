# 开发环境搭建

## 前置条件

- Python ≥ 3.10
- Node.js 20+
- PostgreSQL 16+
- Redis 7+
- Git

## 1. 克隆并初始化

```bash
git clone <repository-url> csagent
cd csagent
git checkout -b feat/local-setup
```

## 2. 安装 Python 依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

## 3. 配置环境变量

```bash
copy .env.example .env
```

至少填写：

- `API_SECRET_KEY`
- `JWT_SECRET_KEY`
- `FIELD_ENCRYPTION_KEY`
- `POSTGRES_URL`
- `REDIS_URL`

## 4. 初始化数据库

本地开发可使用：

```bash
python scripts/init_db.py
alembic upgrade head
python scripts/seed_data.py
```

生产环境只允许使用：

```bash
alembic upgrade head
```

## 5. 启动本地 LLM

```bash
python scripts/start_local_llm.py
```

默认地址：`http://127.0.0.1:8001/v1`

## 6. 启动后端

```bash
uvicorn app.main:app --reload
```

## 7. 启动前端

```bash
cd web/admin
npm ci
npm run dev

cd ../shop
npm ci
npm run dev
```

## 8. 运行质量检查

```bash
python -m compileall -q app scripts
ruff check app scripts tests
pytest tests/unit -q
```

## 9. 提交前检查

- 不提交 `.env`；
- 不提交 `.venv`、`models/`、`node_modules/`；
- 数据库变更必须带 Alembic；
- 架构/安全变化必须带 ADR；
- 禁止直接提交 `main`。
