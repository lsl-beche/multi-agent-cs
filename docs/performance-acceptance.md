# 性能验收标准

## 目标

- 1000 QPS 持续 30 分钟；
- P95 < 300ms，P99 < 800ms；
- 错误率 < 0.1%；
- 500 并发下单无超卖；
- 2000 WebSocket 连接稳定。

## 工具

```bash
pip install locust
locust -f tests/load/locustfile.py --host http://127.0.0.1:8000 --users 1000 --spawn-rate 100
```

小规模基线（本地/CI）：

```bash
python scripts/run_load_test.py --users 20 --run-time 30s
```

## 场景

| 场景 | 配比 |
|---|---|
| 商品浏览 | 50% |
| 下单 | 20% |
| 客服对话 | 20% |
| 管理查询 | 10% |

## 数据库

- RDS PostgreSQL：连接池、慢查询、死锁；
- 热点缓存：商品详情、类目、FAQ；
- 库存扣减：条件 UPDATE；
- 支付回调：幂等 + 唯一约束。

## 验收输出

- Locust HTML 报告；
- Prometheus 指标；
- APM 慢调用；
- 容量建议；
- 回滚/紧急降级方案。
