"""Supervisor 编排 Agent：智能客服的"大脑"入口

职责（三步）：
1. 意图识别：调用 IntentClassifier，把用户原话映射为 12 类客服意图之一
2. 情感识别：调用 sentiment 模块，检测用户的负面情绪（投诉/不满需要更高优先级）
3. 路由决策：根据意图 + 置信度 + 情感，决定：
   - 交给哪个专业子 Agent（知识/订单/售后/促销）
   - 是否直接转人工（投诉、主动转人工、低置信度、强负面情绪）

设计要点：
- Supervisor 本身不调用任何业务工具，只做"判断与分发"，降低耦合
- 路由表 AGENT_ROUTE 是规则化的意图→Agent 映射，方便扩展新意图
- 返回的 state 字段（intent/current_agent/need_human/sentiment）
  由 LangGraph 的 conditional edge 消费，驱动后续节点
"""
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent
from app.agents.graphs.state import AgentState
from app.dialogue.handoff import HandoffManager
from app.dialogue.intent import IntentClassifier


class SupervisorAgent(BaseAgent):
    name = "supervisor"          # Agent 标识，用于日志/指标打标
    description = "主管Agent：统一调度各专业子Agent"

    # ── 意图 → 专业 Agent 的路由表 ──
    # 规则优先级高于语义：列出的意图精确映射；未列出的默认走 knowledge_agent
    AGENT_ROUTE: dict[str, str] = {
        "query_order": "order_agent",
        "track_logistics": "order_agent",
        "payment_issue": "order_agent",
        "return_goods": "aftersale_agent",
        "exchange_goods": "aftersale_agent",
        "product_consult": "knowledge_agent",
        "price_inquiry": "promotion_agent",
        "promotion_consult": "promotion_agent",
        "app_usage": "knowledge_agent",
        # complaint / human_service 直接走人工兜底（need_human=True）
    }

    def __init__(self) -> None:
        """初始化：加载意图分类器（含 BGE 向量预计算）与转人工管理器"""
        super().__init__()
        self.intent_classifier = IntentClassifier()
        self.handoff = HandoffManager()

    def register_tools(self) -> list[BaseTool]:
        # Supervisor 只做编排，不直接调用业务工具（工具由子 Agent 按需调用）
        return []

    async def run(self, state: AgentState) -> dict:
        """执行意图分析与路由决策（LangGraph 节点）

        state 输入：messages（最近对话）、user_id、session_id
        state 输出：
          intent            识别出的意图名
          intent_confidence 意图置信度（0~1）
          current_agent     下一步交给哪个 Agent（不存在的意图默认 knowledge_agent）
          need_human        是否转人工（True 时 workflow 直接走 handoff 节点）
          sentiment         情感分析结果 {score, label, negative, neg_hits, pos_hits}
        """
        last = state["messages"][-1]
        text = last.content if hasattr(last, "content") else str(last)

        # ① 意图识别（BGE 语义相似度 + 关键词兜底）
        result = self.intent_classifier.classify(text)
        # ② 基础转人工判定：投诉/转人工 强制，或置信度低于阈值
        need_human = self.handoff.should_handoff(result.confidence, result.name)

        # ③ 情感识别：强负面情绪时升级转人工（与投诉同权，防止情绪升级）
        from app.dialogue.sentiment import analyze_sentiment
        sentiment = analyze_sentiment(text)
        if sentiment["negative"] and not need_human:
            need_human = True

        # ④ 指标采集：转人工计数（客服大屏/告警用）
        from app.core import metrics
        if need_human:
            metrics.HANDOFFS_TOTAL.inc()

        return {
            "intent": result.name,
            "intent_confidence": result.confidence,
            "current_agent": self.AGENT_ROUTE.get(result.name, "knowledge_agent"),
            "need_human": need_human,
            "sentiment": sentiment,
        }
