# 阶段 D/E · 安全合规/生态开放 + 生产上线进度

> 状态：本地可运行版本完成，云厂商/KMS/第三方压测作为生产依赖待接入。

## D：安全合规与生态开放

- 权限缓存：
  - `AuthService` 按用户缓存角色/权限到 Redis（TTL 300s）；
  - 鉴权中间件实时回源 DB，角色/权限变更后立即失效缓存；
  - 用户创建/更新/封禁后自动 `invalidate_user_permissions`。
- LLM 配额：
  - 每用户按天配额（默认 200 次），Redis 计数，超限转人工提示；
  - HTTP、WebSocket、开放平台统一校验；指标 `csagent_llm_quota_blocked_total`。
- PII 与审计：
  - `app/core/audit.py`：关键敏感操作写 `operation_logs`；
  - 覆盖退款、发票、仲裁、风控黑名单、用户变更、隐私删除；
  - 审计 detail 自动脱敏手机号/邮箱。
- 开放 API：
  - `tenants` + `api_keys` 表与 Alembic 迁移；
  - API Key 仅保存 HMAC 摘要，明文只在创建时返回；
  - `/api/openapi/v1/health|tenant|chat` 公共接口；
  - `/api/openapi/keys|tenants` 管理接口，均记录审计。
- 多商户/ISV 基础：
  - 默认商户 + 商户创建/更新接口；
  - API Key 绑定 tenant_id，为后续数据隔离提供骨架。

## E：生产上线与持续运营

- 质量门禁：`scripts/production_gate.py`（编译/测试/安全/AI 黄金集/Admin 构建）。
- CI：AI 黄金集阈值调整到 0.80，加入 production gate。
- 灰度/回滚：`canary_promote.sh`、`rollback.sh`、ArgoCD 说明。
- 压测：`run_load_test.py` 封装 Locust，输出 CSV。
- 备份恢复：`restore_db.sh` + 现有 `backup_db.sh`。
- 告警：新增 LLM 配额、Token 成本、Agent Trace 错误告警。

## 待外部依赖

- 云 KMS/Secret Manager、WAF、RDS/Tair 加密；
- 真实第三方渗透测试、权限矩阵回归、恢复演练；
- 完整多商户数据隔离（当前为骨架，尚未在所有业务表强制 tenant_id）；
- 1000 QPS / 2000 WS 真实压测需在云端环境执行。

## 本机验证

- 安全验收：通过（ruff + compile + CSP/配额检查）；
- Production Gate：compile / pytest / security / admin-build 全部 PASS；
- 开放 API：创建/鉴权/撤销 API Key、租户接口、AI chat 均通过；
- 数据库迁移：fresh upgrade → downgrade → upgrade 通过；
- 当前测试共 28 项收集，生产门禁内执行通过。
