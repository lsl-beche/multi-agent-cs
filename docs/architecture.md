# 架构设计（第三阶段）

> 完整架构图与说明见 [流程设计.md](../流程设计.md) 第三阶段；目录结构映射见 3.4 节。

## 分层架构与代码映射

| 架构层 | 代码目录 | 职责 |
|--------|---------|------|
| 用户接入层 | `web/` | Web/H5/小程序对话组件、管理后台 |
| API Gateway层 | `app/api/` | 鉴权、限流、路由、日志采集 |
| Agent核心层 | `app/agents/` `app/tools/` `app/dialogue/` | Supervisor编排、专业Agent、工具调用、对话管理 |
| 数据层 | `app/knowledge/` `app/core/` `app/models/` | 向量库、PostgreSQL、Redis |

## 核心数据流
1. 用户提问 → `app/api/`（鉴权、限流）
2. `SupervisorAgent` 分析意图 → 路由至专业Agent
3. 专业Agent执行：检索知识库（`app/knowledge/`）/ 调用业务API（`app/services/`）
4. `ComplianceAgent` 审查回复
5. 流式返回用户（WebSocket）

## 安全设计
- **写操作三段式闭环**：提案（`propose_*`工具）→ 用户确认 → 后端执行（`services/*`）
- 模型不直接修改业务数据库

## TODO
- [ ] 补充部署拓扑图（K8s集群 + 中间件）
- [ ] 补充灰度发布流量切分方案
