# P2 企业级收尾进度

> 分支：`feature/p2-enterprise-completion`  
> 状态：进行中

## 已完成

### 支付 / 物流 / 退款对账

- 新增 `PaymentGateway.verify_callback()` 统一回调验签；
- 微信 / 支付宝 Provider 支持通过 `PAYMENT_GATEWAY_URL` 调用真实渠道；
- 新增 Kuaidi100 / Cainiao 物流 Provider，支持 `LOGISTICS_API_URL` 和 `LOGISTICS_API_KEY`；
- 新增 `app/services/reconciliation_service.py`；
- 新增 `GET /api/admin/reports/reconciliation` 对账接口；
- 退款到账时回补库存、更新订单支付状态并写 outbox。

### 测试与覆盖率

- 新增 `tests/api/test_api_smoke.py`；
- 新增 `tests/services/test_reconciliation_service.py`；
- `tests/conftest.py` 支持 PostgreSQL / Redis testcontainers；
- `pyproject.toml` 增加 coverage 配置；
- CI 增加 `tests/api`、`tests/services` 和覆盖率基线 50%。

### OpenAPI 类型生成

- 新增 `scripts/export_openapi.py`；
- 生成 `docs/openapi.json`；
- 生成 `web/shared/src/types/generated.ts`；
- `web/shared` 提供 `generate:types` 脚本；
- CI 在共享包中重新生成类型。

### 类型接入与测试提升

- `web/shared` 导出 `ApiSchemas`、`paths`、`operations`、`components`；
- 新增 `useChatWidget.ts` 聊天 composable，为 ChatWidget 拆分预留；
- 新增 `tests/unit/test_security.py`、`test_login_guard.py`、`test_gateway_contracts.py`；
- 当前核心模块覆盖率 43%，CI 基线 40%，下一目标 70%。

### 前端分包与大页面基础拆分

- Shop / Admin 增加 `manualChunks`：Vue、Axios、Element Plus、ECharts 独立 chunk；
- 新增 `ProductCard.vue`，商品列表已使用 feature component；
- 商品列表页减少约 100 行模板和业务逻辑。

### 安全与合规基础

- 增加安全响应头；
- PII 加密优先使用 `FIELD_ENCRYPTION_KEY`，兼容旧 key；
- 移除种子账号弱口令，改为环境变量或自动生成；
- 新增 `scripts/security_acceptance.py`；
- CI 新增 `security` 门禁；
- 新增 `docs/security-compliance-checklist.md`、`docs/performance-acceptance.md`。

## 尚未完成

- 真实微信/支付宝商户 SDK 与证书验签；
- 真实物流渠道联调；
- 支付/物流渠道流水下载和自动对账；
- 容器集成测试需在 Docker/CI 真正执行；
- 覆盖率 70% 仍未达到；
- OpenAPI 自动生成类型尚未全面替换手工类型；
- ChatWidget 业务已抽出 composable，模板/样式仍未完全拆分；
- Home、ProductDetail 等大页面仍待继续拆分；
- 第三方渗透测试、PIA、权限矩阵回归、备份恢复演练尚未执行；
- 1000 QPS / 2000 WS 压测尚未完成。
