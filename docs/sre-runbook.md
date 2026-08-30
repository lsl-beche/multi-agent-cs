# SRE 应急预案

## 高优先级场景

| 场景 | 处置步骤 | 负责人 |
|------|---------|--------|
| LLM 故障（5xx/空流） | 检查 `scripts/llm_watchdog.py`；手动重启 llama.cpp；配 `LLM_FALLBACK_URL` 切云端；看转人工激增告警 | AI/客服 |
| PG 不可用 | readiness 摘流；查连接池/磁盘；重启 PG；必要时从备份恢复 | SRE |
| Redis 不可用 | 重启 redis-server（AOF 恢复）；确认限流降级本地生效 | SRE |
| 支付对账差异 | 跑 `reconcile_payments.py --strict`；逐条核对；不可自动修复转财务 | 财务/后端 |
| 转人工激增 | 打开客服大屏；临时加坐席；排障 AI 链路 | 客服主管 |

## 大促预案

1. T-3 天：locust 压测（-u 500）确认余量；扩大 HPA max
2. T-1 天：预扩容、限流阈值上调、备份快照
3. T 日：值班双人（后端+客服）；关闭非核心功能
4. T+1：复盘（容量/故障/改进项）
