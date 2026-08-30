# 多阶段构建：阶段1 编译前端 → 阶段2 后端镜像（含静态产物，供 compose/nginx 使用）

# ── 前端构建 ──
FROM node:20-alpine AS frontend
WORKDIR /build
COPY web/shop/package*.json ./
RUN npm ci || npm install
COPY web/shop/ ./
ARG VITE_API_BASE=/api
ARG VITE_WS_URL=
ENV VITE_API_BASE=$VITE_API_BASE VITE_WS_URL=$VITE_WS_URL
RUN npm run build

# ── 后端运行时 ──
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY models ./models
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
