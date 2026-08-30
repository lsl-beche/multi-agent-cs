# P1：异步数据层与测试基础设施

> 状态：进行中（P1 第一步已完成，服务层异步化仍需推进）

## 已完成

### 异步数据库基础

- `app/core/db.py`：
  - 保留同步 `engine` / `SessionLocal`，供脚本、worker、工具兼容；
  - 新增 `async_engine` / `AsyncSessionLocal`；
  - 使用 `asyncpg` 驱动，URL 自动从 `psycopg` 转为 `asyncpg`。
- `app/api/deps.py`：
  - `get_db()` / `get_async_db()` 返回 `AsyncSession`；
  - 新增 `run_sync()`，在 `AsyncSession` 的 greenlet 中执行现有同步 Service；
  - 所有 API 路由已切换到 `AsyncSession`。

### 路由层异步化

以下路由已从同步 `Session` 迁移到 `AsyncSession`：

- 管理后台：订单、库存、支付、退款、评价、用户、商品、营销、报表、物流、日志；
- C 端：商品、购物车、订单、支付、评价、用户、优惠券；
- 认证、会话、知识库、聊天、人工工单；
- 客服 WebSocket 已使用 `AsyncSession`；
- 健康检查改为异步数据库检查。

### 数据模型与分页

- 金额字段改为 `Decimal`；
- `User` / `Product` / `Inventory` 的 `updated_at` 增加 `onupdate`；
- `Order` / `Inventory` 增加乐观锁 `version`；
- 新增 `role_permissions` 关联表；
- 核心列表查询改用 `paginate()`；
- `admin_logs`、用户订单列表、商品评价列表已替换全量计数。

### 测试基建

- 新增 `tests/conftest.py`；
- 使用 testcontainers 启动 PostgreSQL、Redis；
- 本地无 Docker 时自动 skip；
- 新增 `tests/services/test_order_service.py`：
  - 订单创建 + 原子库存扣减；
  - 库存不足拒绝下单；
  - 订单状态流转 + 取消后库存回补；
- CI 新增 `integration` job，并加入分支保护状态检查。

### 依赖

- `asyncpg`
- `testcontainers[postgres,redis]`
- `docker`

## 尚未完成

- 服务层仍是同步实现，当前通过 `AsyncSession.run_sync()` 运行；
- `dialogue`、`tools`、任务脚本仍使用同步 `SessionLocal`；
- 没有本地 Docker，因此容器集成测试当前在本地 skip；
- 覆盖率尚未达到 70%；
- 真正的“服务层原生 async”转换在后续 P1 收尾阶段完成。

## 验证命令

```bash
python -m compileall -q app scripts tests
ruff check app scripts tests
pytest tests/unit -q
pytest tests/services -q   # 无 Docker 时 skip
python -c "import app.main; print('ok')"
```
