"""Prometheus 指标：HTTP / LLM / 工具 / 业务计数

暴露 /api/metrics 供 Prometheus 抓取（配合 deploy/monitoring/prometheus.yml）。
"""
from prometheus_client import Counter, Gauge, Histogram

# ── HTTP ──
HTTP_REQUESTS = Counter(
    "csagent_http_requests_total", "HTTP 请求数", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "csagent_http_request_duration_seconds",
    "HTTP 请求耗时",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

# ── LLM ──
LLM_CALLS = Counter("csagent_llm_calls_total", "LLM 调用次数", ["task", "provider"])
LLM_DURATION = Histogram(
    "csagent_llm_duration_seconds", "LLM 调用耗时", ["task"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 40, 80, 120),
)
LLM_TOKENS = Counter("csagent_llm_tokens_total", "LLM 生成 token 数（估算）", ["task"])

# ── 工具调用 ──
TOOL_CALLS = Counter("csagent_tool_calls_total", "客服工具调用次数", ["tool"])
TOOL_DURATION = Histogram("csagent_tool_duration_seconds", "客服工具耗时", ["tool"])
TOOL_ERRORS = Counter("csagent_tool_errors_total", "客服工具失败次数", ["tool"])

# ── Agent 运行平台 ──
AGENT_TRACES = Counter("csagent_agent_traces_total", "Agent 运行 trace 数", ["status"])
AGENT_NODES = Counter("csagent_agent_nodes_total", "Agent 节点执行次数", ["node", "status"])
AGENT_TRACE_DURATION = Histogram(
    "csagent_agent_trace_duration_seconds",
    "Agent 单轮运行耗时",
    ["intent"],
    buckets=(1, 3, 6, 10, 20, 40, 60, 90, 120),
)

# ── 模型路由 ──
MODEL_ROUTED = Counter("csagent_model_routed_total", "模型分层路由次数", ["task", "tier"])

# ── 业务事件 ──
ORDERS_CREATED = Counter("csagent_orders_created_total", "创建订单数")
ORDERS_CANCELLED = Counter("csagent_orders_cancelled_total", "关闭/取消订单数", ["reason"])
PAYMENTS_PAID = Counter("csagent_payments_paid_total", "支付成功数", ["channel"])
REFUNDS_COMPLETED = Counter("csagent_refunds_completed_total", "退款到账数")
SHIPMENTS_REFRESHED = Counter("csagent_shipments_refreshed_total", "物流轨迹刷新数")
HANDOFFS_TOTAL = Counter("csagent_handoffs_total", "转人工数")

# ── 在线状态 ──
WS_USERS_ONLINE = Gauge("csagent_ws_users_online", "在线用户 WebSocket 连接数")
WS_ADMINS_ONLINE = Gauge("csagent_ws_admins_online", "在线管理员连接数")
ACTIVE_CHATS = Gauge("csagent_active_chats", "进行中的客服会话数")

# ── PostgreSQL 连接池 ──
PG_POOL_CHECKS = Counter("csagent_pg_pool_checks_total", "PG 连接获取次数")
PG_POOL_CHECKED_OUT = Gauge("csagent_pg_pool_checked_out", "PG 当前借出连接数")

# ── 客服聊天限流 ──
CHAT_RATE_BLOCKED = Counter("csagent_chat_rate_blocked_total", "聊天接口被限流次数")
QUOTA_BLOCKED = Counter("csagent_llm_quota_blocked_total", "用户 AI 日配额拦截数")

# ── 风控 ──
RISK_EVENTS = Counter("csagent_risk_events_total", "风控判定次数", ["action"])
RISK_BLOCKED = Counter("csagent_risk_blocked_total", "风控拦截次数", ["scene"])

# ── 后台记忆任务 ──
MEMORY_TASKS = Counter("csagent_memory_tasks_total", "后台记忆任务数", ["result"])

# ── QA 语义缓存 ──
QA_CACHE_HITS = Counter("csagent_qa_cache_hits_total", "QA 缓存命中数")
QA_CACHE_MISSES = Counter("csagent_qa_cache_misses_total", "QA 缓存未命中数")
