#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=csagent}"
FILE="${1:?用法: ./restore_db.sh <backup.sql.gz>}"

echo "== 恢复数据库 ${PGDATABASE} from ${FILE} =="
gunzip -c "$FILE" | psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE"
echo "== 恢复完成，请运行 alembic upgrade head =="
