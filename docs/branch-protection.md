# 分支保护规范

## 本地仓库已建立的基础

- 默认分支：`main`
- 禁止提交到 `main`：直接提交由团队规范 + CI 门禁约束；
- 远程仓库启用后，必须配置 GitHub 或云效的分支保护。

## 建议保护规则

| 项目 | 值 |
|---|---|
| 受保护分支 | `main` |
| 允许合并方式 | Pull Request / Merge Request |
| 最少审批人数 | 1 人（安全、数据库、支付变更建议 2 人） |
| 要求最新代码 | 开启 strict |
| 必过状态检查 | `backend`、`frontend` |
| 管理员是否绕过 | 否 |
| 合并后删除源分支 | 是 |
| 陈旧审批失效 | 是 |

## GitHub 手工配置

1. 进入仓库 `Settings -> Branches -> Add branch protection rule`；
2. Branch name pattern 填写 `main`；
3. 勾选 `Require pull request reviews before merging`；
4. 勾选 `Require status checks to pass before merging`；
5. 添加状态检查 `backend`、`frontend`；
6. 勾选 `Do not allow bypassing the above settings`；
7. 保存规则。

## 云效手工配置

在云效的“分支管理”中对 `main` 开启：

- 合并请求强制评审；
- 至少 1 名评审人；
- 代码扫描：
  - ruff / mypy / pytest；
  - 安全扫描（SAST）；
  - 数据库迁移检查。

## 本地约束

- 提交前运行：

```bash
python -m compileall -q app scripts
ruff check app scripts tests
pytest tests/unit -q
```

- 禁止提交：

```text
.env
.env.production
models/
.venv/
node_modules/
*.log
```

