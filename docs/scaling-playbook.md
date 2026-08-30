# 规模化运维手册（阶段二）

## 1. 容量模型

| 规模 | DAU | 峰值 QPS | 后端副本 | LLM GPU |
|------|-----|---------|---------|---------|
| 10 万 | 1 万 | 500 | 3-6 | 1-2 张 A10 |
| 100 万 | 10 万 | 5000 | 15-30 | 8-16 张 A100/H20 |
| 1000 万 | 100 万 | 20000 | 60-120 | 32+ 张（多池） |

## 2. 分库分表迁移（PG_SHARD_URLS）

1. 确定分片数（2 的幂，如 64），`user_id` 哈希路由（app/core/sharding.py 已就绪）；
2. 新建分片库并初始化表结构（init_db.py 指向各分片执行）；
3. **双写阶段**：写主库+分片（异步），校验数据一致性；
4. **切读**：读走分片，主库只保留写与历史；
5. **切写**：全部写走分片，主库下线；
6. 回填：历史数据按 user_id 哈希批量迁移，断点续传。

> 路由键统一 user_id；跨分片查询（后台报表）走数仓，不在 OLTP 做 join。

## 3. Redis 集群切换

- 配置 `REDIS_CLUSTER_NODES=[{"host":"...","port":6379},...]`，代码自动切 RedisCluster；
- 会话/缓存键已带业务前缀（csagent:*），迁移时直接透传；
- QA 缓存与限流等易失数据可容忍丢失，无需迁移。

## 4. K8s 弹性

- HPA：backend CPU 60% → 3-30 副本；vLLM 按 running_requests 弹性（vllm.yaml）；
- 大促预案：提前 30 分钟 `kubectl scale deployment csagent-backend --replicas=30`，网关层限流阈值同步上调；
- 多可用区：deployment 加 topologySpreadConstraints（maxSkew=1, whenUnsatisfiable=ScheduleAnyway）；
- 优雅下线：preStop sleep 10 + readiness 探针，保证连接排空。

## 5. 事件驱动演进

- 当前 EVENT_BUS_BACKEND=memory（进程内发布订阅）；
- 生产切 kafka：实现 KafkaEventPublisher 转发 order.created/payment.paid 等事件，
  消费者（通知/数仓/质检）拆为独立服务订阅；
- 消费幂等：消费者按 event_id 去重（Redis SETNX）。

## 6. 可观测性

- Metrics：/api/metrics（Prometheus）+ Grafana 仪表盘（deploy/monitoring/grafana-dashboard.json）；
- Trace：请求级 trace_id 已注入日志（X-Trace-Id），接 OTel 后扩展为 span；
- 告警规则：deploy/monitoring/alert_rules.yml（错误率/延迟/LLM 超时/转人工率突增）；
- 值班：SLO 燃烧告警，P0 15 分钟响应。

## 7. 上线检查清单

- [ ] 生产密钥（JWT/支付网关）已配置，默认密钥守卫生效
- [ ] PG 分片/Redis 集群配置正确，压测验证路由
- [ ] HPA/PDB/ServiceMonitor 已部署
- [ ] 支付回调与对账任务在生产验证
- [ ] 客服黄金集回归通过，语义缓存命中率达标
- [ ] 大促全链路压测（locust）通过，扩容预案演练
