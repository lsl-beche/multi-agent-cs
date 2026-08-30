"""售后工单Agent：退换货咨询、工单创建与流转

工具决策策略与OrderAgent一致：本地小模型走规则驱动，云端大模型走自主tool-calling。
流程：政策解答 -> 槽位检查（订单号）-> 创建工单（写操作，记录到工单系统）
"""
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent, _strip_think_tags
from app.agents.graphs.state import AgentState
from app.agents.order_agent import extract_order_id
from app.config.settings import settings
from app.dialogue.slots import SlotFiller
from app.tools.action_tools import propose_apply_refund
from app.tools.aftersale_tools import get_refund_status, get_ticket_status
from app.tools.policy_tools import check_return_policy
from app.tools.ticket_tools import create_ticket

from loguru import logger

perf_logger = logger.bind(name="perf")


class AfterSaleAgent(BaseAgent):
    name = "aftersale_agent"  # Agent 标识（指标打标用）
    description = "处理退换货、售后工单类咨询"
    system_prompt = (
        "你是电商店铺的售后客服。基于给定的退换货政策回答用户，语气温和、有同理心；"
        "不要编造政策之外的承诺（如退款时效、运费承担以政策文本为准）。"
        "回答尽量简洁，控制在200字以内。"
    )

    def register_tools(self) -> list[BaseTool]:
        """售后工具：政策查询、工单创建、退款进度、工单进度、退款申请提案"""
        return [check_return_policy, create_ticket, get_refund_status, get_ticket_status, propose_apply_refund]

    async def run(self, state: AgentState) -> dict:
        if settings.llm_provider == "local":
            return await self._run_rule_driven(state)
        return await self._run_llm_driven(state)

    async def _run_rule_driven(self, state: AgentState) -> dict:
        """本地规则驱动路径：政策 → 业务数据 → LLM 话术

        规则优先级：
        1. 退款申请（写操作）：命中"申请退款"且带订单号 → 生成退款提案，
           用户确认后由 confirm_action 节点执行
        2. 常规售后：查退换货政策 + 退款进度 + 工单进度（若消息含工单号）
        """
        t_start = time.perf_counter()
        query = state["messages"][-1].content
        intent = state.get("intent", "return_goods")
        user_id = str(state.get("user_id") or "")
        session_id = str(state.get("session_id") or "")

        # ── ① 退款申请（写操作，需确认）：优先处理 ──
        order_id_pre = extract_order_id(query)
        if order_id_pre and ("申请退款" in query or ("退款" in query and ("申请" in query or "帮我退" in query or "要退" in query))):
            proposal = await propose_apply_refund.ainvoke({
                "order_id": order_id_pre, "user_id": user_id,
                "reason": query[:200], "session_id": session_id,
            })
            user_content = (
                f"用户诉求：{query}\n\n退款申请结果：{proposal}\n\n"
                "如果申请需要确认，请告知用户已生成退款提案，并引导回复“确认”执行或“取消”放弃。"
            )
            prompt = [
                SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
                HumanMessage(content=user_content),
            ]
            resp = await self.llm.ainvoke(prompt)
            content = _strip_think_tags(resp.content or "")
            if not content:
                content = f"退款申请处理结果：{proposal}"
            return {"messages": [AIMessage(content=content)], "slots": {"order_id": order_id_pre}}

        # ── ② 阶段三①：查询退换货政策（规则决策）──
        t0 = time.perf_counter()
        policy = await check_return_policy.ainvoke({"category": "general"})
        t_tool = time.perf_counter() - t0
        order_id = extract_order_id(query)
        extra: list[str] = []

        # 退款进度：带订单号时查询（注意与"申请退款"写操作区分）
        if order_id:
            refund = await get_refund_status.ainvoke({"order_id": order_id, "user_id": user_id})
            extra.append(f"退款进度：{refund}")

        # 工单进度：消息中含工单号（TK 开头）时查询
        ticket_m = re.search(r"TK[A-Z0-9_]{4,}", query or "")
        if ticket_m:
            ts = await get_ticket_status.ainvoke({"ticket_id": ticket_m.group(0), "user_id": user_id})
            extra.append(f"工单进度：{ts}")

        extra_text = ("\n".join(extra) + "\n\n") if extra else ""

        if order_id:
            # 槽位齐全：创建售后工单（阶段三②，写操作进入工单系统）
            category = "exchange" if intent == "exchange_goods" else "return"
            t0_ticket = time.perf_counter()
            ticket_result = await create_ticket.ainvoke(
                {"category": category, "description": query, "order_id": order_id}
            )
            t_ticket = time.perf_counter() - t0_ticket
            perf_logger.info(f"[aftersale_agent] tools: policy={t_tool * 1000:.0f}ms, ticket={t_ticket * 1000:.0f}ms, order_id={order_id}")
            user_content = (
                f"用户诉求：{query}\n\n退换货政策：{policy}\n\n工单创建结果：{ticket_result}\n\n"
                f"{extra_text}请综合以上信息回复用户：告知工单已创建、说明政策要点和后续流程。"
            )
        else:
            # 无订单号：基于政策直接回答，LLM 自主判断是否需要引导用户提供订单号
            perf_logger.info(f"[aftersale_agent] policy tool: {t_tool * 1000:.0f}ms (no order_id, LLM decides)")
            user_content = (
                f"用户诉求：{query}\n\n退换货政策：{policy}\n\n{extra_text}"
                "请基于政策解答用户疑问。如果用户的问题需要具体订单号才能进一步处理（如创建退换货工单），"
                "可以在回答完政策后友好地询问订单号；如果只是政策咨询，直接回答即可。"
            )

        # ── ③ 阶段四：LLM 话术生成 ──
        t0 = time.perf_counter()
        prompt = [
            SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
            HumanMessage(content=user_content),
        ]
        resp = await self.llm.ainvoke(prompt)
        t_llm = time.perf_counter() - t0
        content = _strip_think_tags(resp.content or "")
        out_len = len(content)
        perf_logger.info(f"[aftersale_agent] LLM generation: {t_llm * 1000:.0f}ms, output_len={out_len}")
        perf_logger.info(f"[aftersale_agent] TOTAL rule-driven: {(time.perf_counter() - t_start) * 1000:.0f}ms (tools={t_tool * 1000:.0f}ms, llm={t_llm * 1000:.0f}ms)")
        slots = {"order_id": order_id} if order_id else {"need": "order_id"}
        return {"messages": [AIMessage(content=content)], "slots": slots}

    async def _run_llm_driven(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=self.system_prompt)] + list(state["messages"])
        messages = await self._tool_call_loop(messages, max_rounds=3)
        return {"messages": [messages[-1]]}
