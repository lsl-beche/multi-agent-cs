# 后端企业级重构进度

> 分支：`refactor/backend-enterprise`  
> 状态：进行中

## 已完成

### 1. 统一 API 响应与全局异常映射

- `app/api/response.py`：
  - `ApiResponse`
  - `ok()` / `BusinessError` / `NotFoundError` / `ForbiddenError` / `UnauthorizedError`
- `app/main.py`：
  - `BusinessError` 映射；
  - `HTTPException` 统一结构；
  - `RequestValidationError` 422 统一结构；
  - 未捕获异常统一 500 且生产不泄漏堆栈。

### 2. Repository 层

新增 `app/repositories/`：

- `BaseRepository`
- `UserRepository`
- `AddressRepository`
- `CartRepository`
- `ProductRepository`
- `InventoryRepository`
- `OrderRepository`
- `PaymentRepository`
- `RefundRepository`
- `CouponRepository`
- `ReviewRepository`
- `TicketRepository`
- `OutboxRepository`
- `IdempotencyRepository`

### 3. 原生异步核心服务

- `OrderService`：创建订单、取消、确认收货、确认、发货、完成、列表、详情；
- `PaymentService`：发起支付、确认支付、退款审核、退款完成；
- `CouponService`：异步查询和校验；
- `UserService`：地址、资料、密码；
- `CartService`：购物车领域服务；
- `ReviewService`：提交评价、商品评价分页；
- `TicketService`：工单队列、详情、领取、回复、看板；
- `InventoryService`：原子扣减/回补异步入口。

### 4. 路由瘦身

- `shop_cart.py`：仅 HTTP 适配；
- `shop_user.py`：仅 HTTP 适配；
- `shop_payments.py`：仅 HTTP 适配；
- `shop_reviews.py`：仅 HTTP 适配；
- `shop_orders.py`：仅 HTTP 适配；
- `ticket.py`：HTTP/WS 适配，业务移到 `TicketService`；
- `chat.py`：HTTP/WS 适配，业务移到 `chat_pipeline.py`。

### 5. Pydantic DTO

新增请求模型：

- `CartQuantityRequest`
- `CartSelectRequest`
- `PaymentInitiateRequest`
- `PaymentConfirmRequest`
- `ReviewSubmitRequest`
- `AddressCreateRequest`
- `AddressUpdateRequest`
- `ProfileUpdateRequest`
- `PasswordChangeRequest`

### 6. Outbox 与幂等

- `outbox_events` 表；
- `idempotency_keys` 表；
- `app/events/outbox.py`：事务内记录 -> worker 轮询投递；
- `app/services/idempotency_service.py`；
- 订单创建、支付确认、取消订单、退款完成写入 outbox；
- 退款到账会回补库存、更新订单支付状态并投递事件。

## 尚未完成

- `ProductService`、`ReportService` 等部分 Service 仍为同步实现；
- `admin_*` 路由仍通过 `run_sync()` 调用部分同步服务；
- `chat_pipeline` 暂时采用“整包回复”，逐 token 流式优化待恢复；
- 前端类型共享和 API DTO 自动生成未完成；
- API 集成测试、性能测试和覆盖率 70% 未完成；
- Refresh token 吊销、PII 字段加密仍待完成。

## 验证

```bash
python -m compileall -q app scripts tests
ruff check app scripts tests
pytest tests/unit -q
pytest tests/services -q   # 无 Docker 时 skip
```
