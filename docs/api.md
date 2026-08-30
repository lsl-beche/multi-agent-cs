# 接口文档

Base URL：`/api`，除健康检查外均需 `Authorization: Bearer <token>`

## 对话

### POST /api/chat
HTTP对话接口（兜底通道）

请求：
```json
{"session_id": "s123", "user_id": "u456", "message": "我的订单到哪了"}
```
响应：
```json
{"session_id": "s123", "answer": "...", "intent": "track_logistics", "need_human": false, "suggestions": []}
```

### WS /api/chat/ws
WebSocket实时对话（流式）

- 客户端发送：`{"session_id": "...", "user_id": "...", "message": "..."}`
- 服务端推送：`{"type": "chunk", "content": "..."}` / `{"type": "done", "intent": "...", "need_human": false}` / `{"type": "error", "detail": "..."}`

## 会话
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/session/{session_id}/history` | 查询会话历史 |
| DELETE | `/api/session/{session_id}` | 重置会话上下文 |

## 工单
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ticket` | 创建售后工单 |
| GET | `/api/ticket/{ticket_id}` | 查询工单状态 |

## 知识库
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge/items` | 批量新增知识条目 |
| GET | `/api/knowledge/search?q=` | 检索测试 |
| POST | `/api/knowledge/webhook` | 商品变更热更新Webhook |

## 健康检查
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 存活探针 |
| GET | `/api/ready` | 就绪探针 |
