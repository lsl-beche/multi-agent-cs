"""订单处理Agent：订单/物流/支付查询（写操作走「提案 -> 用户确认 -> 后端执行」闭环）

工具决策策略（阶段二）：
- 本地小模型（LLM_PROVIDER=local）：规则驱动——按意图+槽位直接确定工具，
  小模型只做话术生成（3B模型的自由工具决策不稳定，实测会格式漂移）
- 云端大模型：模型自主tool-calling（_tool_call_loop）
"""
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from loguru import logger

from app.agents.base import BaseAgent, _strip_think_tags
from app.agents.graphs.state import AgentState
from app.config.settings import settings
from app.tools.action_tools import propose_address_change, propose_cancel_order, propose_confirm_receipt
from app.tools.logistics_tools import get_shipment_track, track_logistics
from app.tools.order_tools import get_order_detail, get_payment_status, query_order

perf_logger = logger.bind(name="perf")

# 订单号模式：
#   格式1: SO2024001 / DH20250068 (2大写字母+6位以上数字)
#   格式2: 20260802524A0DFC53 (日期8位+hex5字节=18位)
#   格式3: 纯数字8位以上
ORDER_ID_RE = re.compile(r"(?:[A-Z]{2}\d{6,}|\d{8}[A-F0-9]{10})")


def extract_order_id(text: str) -> str | None:
    m = ORDER_ID_RE.search(text or "")
    return m.group(0) if m else None


class OrderAgent(BaseAgent):
    name = "order_agent"  # Agent 标识（指标打标用）
    description = "处理订单状态、物流追踪、支付异常类查询"
    system_prompt = (
        "你是电商店铺的订单客服。根据给定的查询结果回答用户，语气友好简洁；"
        "若结果中带【模拟】标记，需如实说明业务接口暂未对接。不得编造查询结果之外的信息。"
        "回答尽量简洁，控制在200字以内。"
    )

    def register_tools(self) -> list[BaseTool]:
        """挂载的订单类工具：
        query_order（基础状态）、get_order_detail（完整详情）、
        get_payment_status（支付流水）、get_shipment_track（真实物流）、
        track_logistics（模拟兜底）、写操作提案工具（取消/收货/改地址）
        """
        return [
            query_order, get_order_detail, get_payment_status, get_shipment_track, track_logistics,
            propose_cancel_order, propose_confirm_receipt, propose_address_change,
        ]

    async def run(self, state: AgentState) -> dict:
        """订单类问题处理入口：按 LLM 模式分流

        - 本地小模型（local）：_run_rule_driven 规则定工具，小模型只做话术。
          原因：3B 模型自主工具决策不稳定，实测格式漂移率高；
        - 云端大模型：_run_llm_driven 走标准 tool-calling，由模型自主决策。
        """
        if settings.llm_provider == "local":
            return await self._run_rule_driven(state)
        return await self._run_llm_driven(state)

    async def _run_rule_driven(self, state: AgentState) -> dict:
        """本地小模型路径：规则定工具（阶段二~三）+ LLM 做话术（阶段四）

        规则判定顺序：
        1. 写操作优先：取消/确认收货/改地址 → 生成"待确认提案"，
           等用户回复"确认"后由 workflow 的 confirm_action 节点执行
        2. 无订单号：交由 LLM 判断是否需要引导用户补充
        3. 按意图选查询工具：物流→真实轨迹、支付→流水、其他→完整订单详情
        """
        t_start = time.perf_counter()
        query = state["messages"][-1].content
        intent = state.get("intent", "query_order")
        # extract_order_id：正则抽取订单号（SO/DH+6位数字，或 18 位日期型）
        order_id = extract_order_id(query)
        user_id = str(state.get("user_id") or "")
        session_id = str(state.get("session_id") or "")

        # ── ① 写操作优先：取消订单 / 确认收货 / 修改地址 ──
        if order_id:
            if "取消" in query:
                # 生成取消提案（写操作闭环第一步：提案→用户确认→执行）
                result = await propose_cancel_order.ainvoke({
                    "order_id": order_id, "user_id": user_id,
                    "reason": query[:100], "session_id": session_id,
                })
                return await self._finish_with_tool_result(query, result, order_id)
            if "确认收货" in query or "确认收" in query:
                # 生成确认收货提案
                result = await propose_confirm_receipt.ainvoke({
                    "order_id": order_id, "user_id": user_id, "session_id": session_id,
                })
                return await self._finish_with_tool_result(query, result, order_id)
            if any(k in query for k in ("改地址", "修改地址", "改收货地址", "换地址", "地址改")):
                # 从用户话术中正则抽取新地址（"改成/改为/寄到..."后的内容）
                m = re.search(r"(?:改成|改为|修改为|送到|寄到)\s*([^\s].{4,})", query)
                new_address = m.group(1).strip() if m else ""
                if new_address:
                    result = await propose_address_change.ainvoke({
                        "order_id": order_id, "new_address": new_address,
                        "user_id": user_id, "session_id": session_id,
                    })
                    return await self._finish_with_tool_result(query, result, order_id)

        # ── ② 无订单号：让 LLM 判断是否需要引导提供订单号 ──
        if not order_id:
            t0 = time.perf_counter()
            prompt = [
                SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
                HumanMessage(content=(
                    f"用户问题：{query}\n\n"
                    "注意：用户未提供订单号。如果这是一个需要订单号才能回答的问题（如查询具体订单状态、物流进度），"
                    "请友好地引导用户提供订单号。如果是一般性问题（如发货时效、运费政策、支付方式），可以直接回答。"
                )),
            ]
            resp = await self.llm.ainvoke(prompt)
            t_llm = time.perf_counter() - t0
            # 清洗 <think> 标签
            content = _strip_think_tags(resp.content or "")
            perf_logger.info(f"[order_agent] no order_id, LLM decision: {t_llm * 1000:.0f}ms, answer_len={len(content)}")
            perf_logger.info(f"[order_agent] TOTAL rule-driven: {(time.perf_counter() - t_start) * 1000:.0f}ms")
            return {"messages": [AIMessage(content=content)], "slots": {"need": "order_id"}}

        # ── ③ 阶段三：按意图确定并执行工具（规则决策）──
        # 工具入参都带 user_id 做订单归属校验（越权返回"无权查看"）
        t0 = time.perf_counter()
        if intent == "track_logistics":
            result = await get_shipment_track.ainvoke({"order_id": order_id, "user_id": user_id})
        elif intent == "payment_issue":
            result = await get_payment_status.ainvoke({"order_id": order_id, "user_id": user_id})
        else:
            result = await get_order_detail.ainvoke({"order_id": order_id, "user_id": user_id})
        t_tool = time.perf_counter() - t0
        perf_logger.info(f"[order_agent] tool: {t_tool * 1000:.0f}ms, intent={intent}, order_id={order_id}")

        # ── ④ 阶段四：LLM 把工具结果转写成客服话术 ──
        t0 = time.perf_counter()
        prompt = [
            SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
            HumanMessage(content=f"用户问题：{query}\n\n查询结果：{result}"),
        ]
        resp = await self.llm.ainvoke(prompt)
        t_llm = time.perf_counter() - t0
        content = _strip_think_tags(resp.content or "")
        out_len = len(content)
        perf_logger.info(f"[order_agent] LLM generation: {t_llm * 1000:.0f}ms, output_len={out_len}")
        perf_logger.info(f"[order_agent] TOTAL rule-driven: {(time.perf_counter() - t_start) * 1000:.0f}ms (tool={t_tool * 1000:.0f}ms, llm={t_llm * 1000:.0f}ms)")
        return {"messages": [AIMessage(content=content)], "slots": {"order_id": order_id}}

    async def _finish_with_tool_result(self, query: str, result: str, order_id: str) -> dict:
        """写操作提案结果 -> LLM 转话术"""
        prompt = [
            SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
            HumanMessage(content=f"用户问题：{query}\n\n操作结果：{result}\n\n"
                                "如果操作需要用户确认，请清晰告知用户已生成提案，并引导回复“确认”或“取消”。"),
        ]
        resp = await self.llm.ainvoke(prompt)
        content = _strip_think_tags(resp.content or "")
        if not content:
            content = f"操作结果：{result}"
        return {"messages": [AIMessage(content=content)], "slots": {"order_id": order_id}}

    async def _run_llm_driven(self, state: AgentState) -> dict:
        """云端大模型路径：模型自主tool-calling循环"""
        messages = [SystemMessage(content=self.system_prompt)] + list(state["messages"])
        messages = await self._tool_call_loop(messages, max_rounds=3)
        return {"messages": [messages[-1]]}
