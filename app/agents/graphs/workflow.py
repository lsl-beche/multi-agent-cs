"""LangGraph 状态图：Supervisor 编排流程（节点与边定义）

完整流程：

  用户提问
    ▼
  confirm_action（写操作确认节点，最先执行）
    │ 无待办 → supervisor；有待办+确认 → execute_* → 结束
    ▼
  supervisor（意图+情感识别，路由分发）
    ├─ 投诉/转人工/低置信度/强负面 → handoff（创建工单+通知管理员）
    ├─ 知识类 → knowledge_agent →（纯知识高置信度跳过合规）→ 输出
    ├─ 订单类 → order_agent → compliance
    ├─ 售后类 → aftersale_agent → compliance
    └─ 促销类 → promotion_agent → compliance

设计要点：
- confirm_action 作为"入口前置节点"，保证写操作确认闭环优先于意图路由
  （否则用户回复"确认"会被当作普通消息，误入知识 Agent 造成幻觉应答）
- 各 Agent 节点用 _timed 包装，输出节点耗时到 perf 日志（可观测性）
- 条件边由三个函数驱动：_route_after_confirm / _route_after_supervisor /
  _route_after_knowledge_agent，分别处理"有无待办/是否转人工/是否跳过合规"
"""
import time

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from loguru import logger

from app.agents.graphs.state import AgentState

perf_logger = logger.bind(name="perf")

HANDOFF_MESSAGE = (
    "您的问题我已记录，正在为您转接人工客服。"
    "人工客服工作时间9:00-22:00，请稍候；非工作时间留言将在次日优先处理。"
)

# 写操作确认闭环：用户回复确认/取消 的识别词
_CONFIRM_WORDS = ("确认", "同意", "没问题", "就这样", "可以", "好的")
_CANCEL_WORDS = ("不用了", "算了", "不要了", "取消吧", "不办了")


def _is_confirm(text: str) -> bool:
    """判定是否为"确认"回复

    限定 len<=6 是安全设计：避免把"确认收货 SO…"这类新请求
    误判为对上一个提案的确认（否则会错误执行上一个待办动作）。
    """
    if any(w in text for w in ("不确认", "不确认了")):
        return False
    return any(w in text for w in _CONFIRM_WORDS) and len(text) <= 6


def _is_cancel(text: str) -> bool:
    """判定是否为"取消待办"回复（同样限制长度，避免误伤新请求）"""
    return len(text) <= 10 and any(w in text for w in _CANCEL_WORDS)


async def _run_pending_action(pending: dict) -> str:
    """执行待确认动作（propose_* → 用户确认 → execute_*）

    pending 结构：{"action": 动作名, "params": 参数字典, "created_at": 时间戳}
    按动作名分派到对应 execute 工具（工具内部会再次做归属/状态校验），
    并把工具返回的 JSON 转成用户友好的话术。
    """
    import json as _json

    from app.tools.action_tools import (
        execute_address_change,
        execute_apply_refund,
        execute_cancel_order,
        execute_confirm_receipt,
    )

    action = pending.get("action")
    params = pending.get("params", {})
    raw = "抱歉，未识别的操作。"
    try:
        if action == "cancel_order":
            raw = await execute_cancel_order.ainvoke(params)
        elif action == "confirm_receipt":
            raw = await execute_confirm_receipt.ainvoke(params)
        elif action == "apply_refund":
            raw = await execute_apply_refund.ainvoke(params)
        elif action == "address_change":
            raw = await execute_address_change.ainvoke(params)
    except Exception as e:
        return f"操作执行失败：{e}"
    # 将工具返回的 JSON 转成用户友好的话术
    try:
        d = _json.loads(raw)
    except Exception:
        return raw
    if isinstance(d, dict) and d.get("error"):
        return f"抱歉，操作未能完成：{d.get('message', '未知原因')}"
    if action == "cancel_order":
        return f"已完成：订单 {params.get('order_id', '')} 已取消，库存已释放。"
    if action == "confirm_receipt":
        return "已完成：已为您确认收货，订单状态更新为已完成，欢迎回来评价～"
    if action == "apply_refund":
        return f"已完成：退款申请已提交（单号 {d.get('refund_no', '')}，金额 ¥{d.get('amount', '')}），将按售后流程审核。"
    if action == "address_change":
        return f"已完成：订单收货地址已更新为：{d.get('new_address', '')}"
    return raw


async def confirm_action_node(state: AgentState) -> dict:
    """确认节点：若会话有待确认动作且用户回复确认/取消，则执行或放弃，直接结束本轮"""
    from app.dialogue.action_store import clear_pending, get_pending

    session_id = state.get("session_id", "")
    messages = state.get("messages", [])
    if not messages:
        return {}
    last = messages[-1]
    text = last.content if hasattr(last, "content") else str(last)
    pending = get_pending(session_id)
    if not pending:
        # 没有待确认操作时，若用户只是说了“确认/好的”等确认词，礼貌说明并结束，避免被其他Agent误答
        if _is_confirm(text):
            return {
                "messages": [AIMessage(content="当前没有需要确认的操作，您可以直接咨询其他问题。")],
                "current_agent": "end",
            }
        return {}
    if _is_cancel(text):
        clear_pending(session_id)
        return {
            "messages": [AIMessage(content="好的，已取消刚才的操作，您可以继续咨询其他问题。")],
            "current_agent": "end",
        }
    if _is_confirm(text):
        result = await _run_pending_action(pending)
        clear_pending(session_id)
        return {"messages": [AIMessage(content=result)], "current_agent": "end"}
    return {}


def _route_after_confirm(state: AgentState) -> str:
    """confirm_action 后置路由：执行过（current_agent=end）→ 结束，否则进 supervisor"""
    if state.get("current_agent") == "end":
        return "end"
    return "supervisor"


# 可跳过合规审查的意图（纯知识类，无业务操作风险）
_SKIP_COMPLIANCE_INTENTS = {"product_consult", "price_inquiry", "promotion_consult", "app_usage", "chitchat"}


async def human_handoff_node(state: AgentState) -> dict:
    """人工兜底节点：投诉/主动要求人工/低置信度时进入"""
    session_id = state.get("session_id", "")
    intent = state.get("intent", "unknown")
    messages = state.get("messages", [])
    last_msg = messages[-1].content if messages else ""

    # 构建对话上下文摘要（取最近5轮，供管理员快速了解情况）
    context_lines: list[str] = []
    for m in messages[-10:]:
        role_label = "用户" if getattr(m, "type", "") == "human" or hasattr(m, "type") is False else "客服"
        content = getattr(m, "content", str(m)) if hasattr(m, "content") else str(m)
        ctx_role = "用户" if role_label == "用户" or (hasattr(m, "__class__") and m.__class__.__name__ == "HumanMessage") else "系统"
        if hasattr(m, "__class__"):
            role_display = "用户" if m.__class__.__name__ == "HumanMessage" else "客服"
        else:
            role_display = "用户" if getattr(m, "role", "") == "user" else "客服"
        context_lines.append(f"[{role_display}] {content[:120]}")

    summary = "\n".join(context_lines[-6:])  # 最近3轮对话
    reason = f"意图={intent}, 用户问题={last_msg[:200]}"

    # 异步触发转接（不阻塞主流程）
    import asyncio

    from app.dialogue.handoff import HandoffManager

    handoff = HandoffManager()
    asyncio.create_task(handoff.transfer(session_id, reason, conversation_context=summary))

    return {"messages": [AIMessage(content=HANDOFF_MESSAGE)]}


def _route_after_supervisor(state: AgentState) -> str:
    """Supervisor之后的路由：需转人工优先，否则按意图分发"""
    if state.get("need_human"):
        return "handoff"
    return state.get("current_agent", "knowledge_agent")


def _route_after_knowledge_agent(state: AgentState) -> str:
    """知识Agent之后的路由：纯知识类意图直接输出，跳过合规审查（无业务操作风险）"""
    intent = state.get("intent", "")
    if intent in _SKIP_COMPLIANCE_INTENTS:
        return "end"
    return "compliance_agent"


def _timed(name: str, fn):
    """为 Agent 节点添加耗时日志的装饰器"""
    async def _wrapper(state: AgentState) -> dict:
        from app.agents.trace import set_current_trace_id, trace_store
        from app.core.metrics import AGENT_NODES

        t0 = time.perf_counter()
        trace_id = state.get("trace_id", "")
        set_current_trace_id(trace_id)
        node_status = "ok"
        try:
            result = await fn(state)
        except Exception as exc:
            node_status = "error"
            trace_store.record_node(trace_id, name, "error",
                                    (time.perf_counter() - t0) * 1000, str(exc)[:300])
            AGENT_NODES.labels(node=name, status="error").inc()
            raise
        finally:
            elapsed = time.perf_counter() - t0
            intent = state.get("intent", "")
            trace_store.record_node(trace_id, name, node_status, elapsed * 1000, intent)
            AGENT_NODES.labels(node=name, status=node_status).inc()
            perf_logger.info(f"[workflow] {name}: {elapsed * 1000:.0f}ms (intent={intent})")
            set_current_trace_id("")
        return result
    return _wrapper


def build_workflow():
    # 延迟导入，避免模块级循环依赖
    from app.agents.aftersale_agent import AfterSaleAgent
    from app.agents.compliance_agent import ComplianceAgent
    from app.agents.knowledge_agent import KnowledgeAgent
    from app.agents.order_agent import OrderAgent
    from app.agents.promotion_agent import PromotionAgent
    from app.agents.supervisor import SupervisorAgent

    supervisor = SupervisorAgent()
    knowledge_agent = KnowledgeAgent()
    order_agent = OrderAgent()
    aftersale_agent = AfterSaleAgent()
    compliance_agent = ComplianceAgent()
    promotion_agent = PromotionAgent()

    graph = StateGraph(AgentState)
    graph.add_node("supervisor", _timed("supervisor", supervisor.run))
    graph.add_node("confirm_action", _timed("confirm_action", confirm_action_node))
    graph.add_node("knowledge_agent", _timed("knowledge_agent", knowledge_agent.run))
    graph.add_node("order_agent", _timed("order_agent", order_agent.run))
    graph.add_node("aftersale_agent", _timed("aftersale_agent", aftersale_agent.run))
    graph.add_node("promotion_agent", _timed("promotion_agent", promotion_agent.run))
    graph.add_node("handoff", _timed("handoff", human_handoff_node))
    graph.add_node("compliance_agent", _timed("compliance_agent", compliance_agent.run))

    graph.set_entry_point("confirm_action")
    graph.add_conditional_edges(
        "confirm_action",
        _route_after_confirm,
        {"supervisor": "supervisor", "end": END},
    )
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "knowledge_agent": "knowledge_agent",
            "order_agent": "order_agent",
            "aftersale_agent": "aftersale_agent",
            "promotion_agent": "promotion_agent",
            "handoff": "handoff",
        },
    )
    # 知识类问题高置信度可跳过合规审查直接输出，减少延迟
    graph.add_conditional_edges(
        "knowledge_agent",
        _route_after_knowledge_agent,
        {"compliance_agent": "compliance_agent", "end": END},
    )
    graph.add_edge("order_agent", "compliance_agent")
    graph.add_edge("aftersale_agent", "compliance_agent")
    graph.add_edge("promotion_agent", "compliance_agent")
    graph.add_edge("handoff", END)  # 人工兜底为固定话术，无需合规审查
    graph.add_edge("compliance_agent", END)

    return graph.compile()


_workflow = None


def get_workflow():
    """单例获取编译后的工作流（避免每请求重复构建Agent与工具绑定）"""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


# 使用方式：
#   workflow = get_workflow()
#   result = await workflow.ainvoke({"messages": [HumanMessage(content="龙井怎么泡")], "session_id": "s1", "user_id": "u1", "slots": {}})
