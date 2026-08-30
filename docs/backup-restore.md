# 备份与恢复演练手册

## 备份策略

| 对象 | 方式 | 频率 | 保留 |
|------|------|------|------|
| PostgreSQL | `pg_dump` 逻辑备份 | 每日（compose backup 容器或 cron） | 7 天 |
| Chroma 向量库 | 目录 tar 快照 | 每日 | 7 天 |
| Redis | AOF 持久化（生产建议主从） | 持续 | 集群治理 |

手动执行：`bash scripts/backup_db.sh`（本机需 pg_dump；Deploy 容器亦内置）。

## 恢复演练（每季度一次）

1. 创建临时库并恢复：
   `gunzip -c backup/csagent-*.sql.gz | psql -U csagent -d csagent_restore`
2. 恢复向量库并校验计数：
   `tar -xzf backup/vectordb-*.tar.gz -C ./data`，再用 `get_vectorstore()._collection.count()` 校验
3. 一致性校验：`python scripts/reconcile_payments.py --strict`
4. 启动临时后端并跑 `python scripts/eval_dialogue.py`

## 验收标准

- 恢复后表数量与线上一致（Alembic 基线 + 增量）
- 支付对账零差异
- 黄金集评测 ≥95%
- RPO ≤ 1 天（每日备份），目标 RTO ≤ 30 分钟
