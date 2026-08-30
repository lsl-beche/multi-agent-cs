"""促销Agent：优惠券、积分、活动与价格类咨询（本地规则驱动 + 云端tool-calling）"""
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent, _strip_think_tags
from app.agents.graphs.state import AgentState
from app.config.settings import settings
from app.tools.promotion_tools import claim_coupon, get_member_info, get_my_coupons, get_points


class PromotionAgent(BaseAgent):
    name = "promotion_agent"  # Agent 标识（指标打标用）
    description = "处理优惠券、促销活动、积分与价格类咨询"
    system_prompt = (
        "你是电商店铺的促销客服。基于给定的查询结果回答优惠券、积分、活动问题，"
        "语气友好简洁；不得编造查询结果之外的信息。"
        "回答尽量简洁，控制在200字以内。"
    )

    def register_tools(self) -> list[BaseTool]:
        """促销工具：我的优惠券、领取优惠券（写）、积分查询、会员信息"""
        return [get_my_coupons, claim_coupon, get_points, get_member_info]

    async def run(self, state: AgentState) -> dict:
        """促销类问题入口：本地规则驱动 / 云端 tool-calling 双模式"""
        if settings.llm_provider == "local":
            return await self._run_rule_driven(state)
        return await self._run_llm_driven(state)

    async def _run_rule_driven(self, state: AgentState) -> dict:
        """本地规则驱动：先查券/积分/会员，再按需识别"领券"意图

        优势：促销问题答案高度依赖用户数据（券/积分），
        规则层直接并行查询，再交给 LLM 组织话术。
        """
        query = state["messages"][-1].content
        uid = str(state.get("user_id") or "")

        # ① 基础数据：我的优惠券 + 积分（登录用户才有值，游客返回提示）
        parts = []
        coupons = await get_my_coupons.ainvoke({"user_id": uid})
        parts.append(f"我的优惠券：{coupons}")
        points = await get_points.ainvoke({"user_id": uid})
        parts.append(f"我的积分：{points}")
        # 会员类问题额外查会员等级（按积分阈值推导）
        if "会员" in query:
            member = await get_member_info.ainvoke({"user_id": uid})
            parts.append(f"会员信息：{member}")

        # ② 领券意图：从话术中提取券号（"优惠券N / 领券N"），命中且含"领取"才执行
        m = re.search(r"优惠券\s*[#第号]?\s*(\d+)", query) or re.search(r"领\S*券\s*(\d+)", query)
        if "领取" in query or "领券" in query or "领一张" in query:
            if m:
                # 明确券号：直接调用领券工具（写操作，校验有效期/库存/上限）
                claim = await claim_coupon.ainvoke({"user_id": uid, "coupon_id": int(m.group(1))})
                parts.append(f"领券结果：{claim}")
            else:
                # 未明确券号：落提示，让 LLM 引导用户选择
                parts.append("提示：用户想领券但未明确券号，请询问要领取哪张券。")

        # ③ LLM 组织话术（基于查询结果，不编造）
        tool_text = "\n".join(parts)
        prompt = [
            SystemMessage(content=self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"),
            HumanMessage(content=f"用户问题：{query}\n\n查询结果：\n{tool_text}"),
        ]
        resp = await self.llm.ainvoke(prompt)
        content = _strip_think_tags(resp.content or "")
        return {"messages": [AIMessage(content=content)]}

    async def _run_llm_driven(self, state: AgentState) -> dict:
        """云端模式：标准 tool-calling，由模型自主决定调用哪些促销工具"""
        messages = [SystemMessage(content=self.system_prompt)] + list(state["messages"])
        messages = await self._tool_call_loop(messages, max_rounds=3)
        return {"messages": [messages[-1]]}
