# Contributing

## 分支规范

- 永久分支：`main`（受保护）、`develop`（可选）；
- 功能分支：`feat/<short-name>`；
- 修复分支：`fix/<short-name>`；
- 安全分支：`security/<short-name>`；
- 发布分支：`release/<version>`；
- 禁止直接提交 `main`。

## 提交信息

建议使用 Conventional Commits：

```text
feat(order): support atomic stock deduction
fix(auth): reject forged WebSocket tokens
chore(ci): enable coverage gate
docs(adr): record L2 enterprise target
```

## 设计决策

任何影响架构、安全、数据、部署的变更，必须在合并前新增一条 ADR：

```text
docs/adr/NNNN-short-title.md
```

## 数据库变更

- 必须同时提供 Alembic upgrade/downgrade；
- 必须说明兼容性、回滚和上线顺序；
- 不允许直接修改生产数据库。

## 安全要求

- 禁止提交 `.env`、密钥、token、生产连接串；
- 涉及权限/认证的修改必须附测试；
- 优先使用 `Depends(require_permission(...))`，禁止 fail-open。

## 回滚要求

- 发布前必须有回滚方案；
- 数据库迁移必须向后兼容；
- 所有 release 必须保留上一版镜像和版本配置。
