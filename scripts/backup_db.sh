#!/usr/bin/env bash
# 数据库 + 向量库备份（cron/容器定时执行；保留 KEEP_DAYS 天）
set -euo pipefail

DB_URL="${POSTGRES_URL:-postgresql+psycopg://postgres:password@localhost:5432/csagent}"
BACKUP_DIR="${BACKUP_DIR:-./backup}"
KEEP_DAYS="${KEEP_DAYS:-7}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d%H%M)"

# 1) PostgreSQL 逻辑备份
echo "== 备份 PostgreSQL =="
pg_dump --dbname="${DB_URL/postgresql+psycopg/postgresql}" | gzip > "$BACKUP_DIR/csagent-$STAMP.sql.gz"

# 2) 向量库目录快照（Chroma 持久化）
echo "== 备份向量库 =="
tar -czf "$BACKUP_DIR/vectordb-$STAMP.tar.gz" -C ./data vectordb

# 3) 保留期清理
find "$BACKUP_DIR" -name "*.gz" -mtime +"$KEEP_DAYS" -delete
echo "备份完成: $BACKUP_DIR（保留 ${KEEP_DAYS} 天）"
