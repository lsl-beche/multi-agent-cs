"""槽位填充：记录/引导用户补充任务所需信息（订单号、退换原因、新地址）

用途：部分客服任务需要结构化信息才能执行，例如：
- 查订单需要 order_id；退换货需要 order_id + reason；
- 改地址需要 order_id + new_address。

SlotFiller 只做"缺什么/怎么问"，不做 LLM 抽取；
实际抽取（如订单号正则、地址正则）在各 Agent 的规则分支中完成。
"""

# 各意图所需的必填槽位
REQUIRED_SLOTS: dict[str, list[str]] = {
    "query_order": ["order_id"],
    "track_logistics": ["order_id"],
    "return_goods": ["order_id", "reason"],
    "exchange_goods": ["order_id", "reason"],
    "propose_address_change": ["order_id", "new_address"],
}

# 槽位引导话术
SLOT_PROMPTS: dict[str, str] = {
    "order_id": "请提供您的订单号（可在「我的订单」中查看），我帮您查询。",
    "reason": "请问退换货的原因是什么呢？（如：质量问题/尺码不合适/不喜欢）",
    "new_address": "请提供新的收货地址（含收件人、电话、详细地址）。",
}


class SlotFiller:
    def missing_slots(self, intent: str, slots: dict) -> list[str]:
        """计算当前意图还缺少哪些必填槽位"""
        required = REQUIRED_SLOTS.get(intent, [])
        return [s for s in required if not slots.get(s)]

    def build_prompt_question(self, slot: str) -> str:
        """生成引导用户补充槽位的话术"""
        return SLOT_PROMPTS.get(slot, f"请补充信息：{slot}")

    def is_ready(self, intent: str, slots: dict) -> bool:
        return not self.missing_slots(intent, slots)
