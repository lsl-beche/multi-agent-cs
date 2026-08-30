"""全局会话状态：LangGraph State Schema 定义

说明：LangGraph 的 State 是"字典 + reducer"结构——
- 所有字段可在节点之间传递（已返回并合并的字段对后续节点可见）
- messages 使用 add_messages reducer：每个节点返回的新消息会追加进历史，
  自动实现"阶段五：多轮记忆写回"，无需手动维护消息数组

字段分组：
- 消息与会话：messages / session_id / user_id（跨节点共享的上下文）
- 对话管理：intent / intent_confidence / slots（意图理解与信息抽取）
- 编排控制：current_agent（Supervisor 的下一步决策）/ need_human（转人工标记）
- 质量保障：compliance_passed（合规审查结果）
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # 消息历史（add_messages reducer 自动实现阶段五：记忆写回）
    # 结构：[SystemMessage/HumanMessage/AIMessage]，顺序即对话顺序
    messages: Annotated[list, add_messages]

    # 会话标识：session_id 用于 Redis 会话记忆/待确认动作；
    # user_id 用于订单归属校验、用户偏好记忆、向量记忆
    session_id: str
    user_id: str

    # 意图与槽位（对话管理）：
    # intent        识别出的意图名（12 类）
    # slots         槽位字典（如 {"order_id": "SO2024001"}），供子 Agent 决策
    intent: str
    intent_confidence: float
    slots: dict

    # Supervisor 路由结果：下一步进入的子 Agent 节点名
    current_agent: str

    # 合规审查结果：False 时 workflow 会转人工兜底
    compliance_passed: bool

    # 是否转人工：True 时直接进入 handoff 节点（创建工单+通知管理员）
    need_human: bool

    # 情感分析结果（Supervisor 写入，供日志/转人工决策追溯）
    sentiment: dict
