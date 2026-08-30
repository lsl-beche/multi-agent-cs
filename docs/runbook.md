# 运维手册（第七阶段）

## 监控指标
- **业务指标**：咨询量、解决率、转人工率（目标 <20%-30%）、CSAT
- **技术指标**：响应延迟 P50/P95/P99（目标 <1秒）、错误率、GPU/CPU利用率

## 告警处理
| 告警 | 处理动作 |
|------|---------|
| HighErrorRate（错误率>5%） | 检查LLM API配额与下游业务API可用性；必要时切换备用模型 |
| HighLatency（P95>1s） | 检查向量库负载；临时调低检索Top-K；扩容Pod |
| ServiceDown | 检查Pod状态 `kubectl get pods`；按回滚预案执行 |

## 回滚预案
1. K8s滚动回滚：`kubectl rollout undo deployment/csagent`
2. 流量切回人工客服兜底（网关侧开关）
3. 保留故障时段日志用于复盘

## 例行维护
- **每周**：运行 `scripts/export_logs.py` 导出未解决问题 → 补充知识库 → 重新入库
- **每月**：评估RAG效果（Top-K、分块策略、Rerank模型）；评审违禁词库
