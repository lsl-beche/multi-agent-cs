"""合规审查Agent：LLM 驱动的内容安全审核 + 关键词快速预筛

双阶段审查：
  阶段一：关键词快速预筛（<1ms）
  阶段二：LLM 语义审核（仅预筛存疑时触发），检查虚假承诺/价格误导/敏感内容
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent
from app.agents.graphs.state import AgentState
from app.core.llm import get_llm_for_task

# 关键词快速预筛：广告法极限词 + 敏感词
_FAST_FILTER_WORDS = [
    "绝对", "百分百", "全网最低", "第一", "顶级", "国家级", "最佳",
    "唯一", "永久", "万能", "特效药", "根治", "保证治愈",
]

_COMPLIANCE_PROMPT = (
    "你是一个内容安全审核助理。请检查以下客服回复是否存在合规风险：\n\n"
    "审核规则：\n"
    "1. 虚假承诺：如「保证」「100%有效」「绝对能治好」等 —— 不合格\n"
    "2. 价格误导：如「全网最低」「比任何店都便宜」等 —— 不合格\n"
    "3. 贬低竞品：如「别家都是假货」「其他店骗人」等 —— 不合格\n"
    "4. 敏感内容：涉及政治、色情、暴力、违法信息 —— 不合格\n"
    "5. 医疗建议：声称茶叶能治病或替代药物 —— 不合格\n\n"
    "请只回复一个词：「合格」或「不合格」。\n"
    "如果是不合格，在后面用一句话说明原因。\n\n"
    "客服回复内容：\n{content}"
)


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"  # Agent 标识（指标打标用）
    description = "审查AI回复内容，过滤违规表述"

    def register_tools(self) -> list[BaseTool]:
        # 合规审查不需要外部工具：纯文本规则 + LLM 语义审核
        return []

    async def run(self, state: AgentState) -> dict:
        """合规审查节点：双阶段审核

        阶段一（快）：关键词预筛（广告法极限词/敏感词），<1ms；
                    未命中直接放行（绝大多数回复不会触发，避免每次调 LLM）
        阶段二（慢）：仅预筛存疑时调 LLM 语义审核，
                    检查虚假承诺/价格误导/贬低竞品/医疗建议等

        输出：
          compliance_passed=True   → 回复通过，正常返回用户
          compliance_passed=False  → 回复不合格，workflow 转人工兜底
        """
        last_msg = state["messages"][-1] if state.get("messages") else None
        if not last_msg:
            return {"compliance_passed": True}
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        if not content:
            return {"compliance_passed": True}

        # ── 阶段一：关键词快速预筛 ──
        # 命中极限词才进入 LLM 审核，未命中直接放行（省一次 LLM 调用）
        hit_words = [w for w in _FAST_FILTER_WORDS if w in content]
        if not hit_words:
            return {"compliance_passed": True}

        # ── 阶段二：LLM 语义审核（仅预筛命中时触发）──
        try:
            llm = get_llm_for_task("compliance_agent", max_tokens=64)
            prompt_content = _COMPLIANCE_PROMPT.format(content=content[:800])
            resp = await llm.ainvoke([
                SystemMessage(content="你是内容安全审核助手，请严格按规则审核。直接回答，不要使用 <think> 标签。"),
                HumanMessage(content=prompt_content),
            ])
            result = (resp.content or "").strip()

            if "不合格" in result:
                # 审核不过：标记转人工，用固定话术替换原回复
                reason = result.replace("不合格", "").strip().lstrip("：:").strip()
                return {
                    "compliance_passed": False,
                    "need_human": True,
                    "messages": [AIMessage(
                        content="抱歉，该回复内容需要人工审核确认，已为您转接人工客服。"
                    )],
                }
        except Exception:
            pass  # LLM 不可用时，按关键词命中保守处理（维持放行，避免误伤）

        return {"compliance_passed": True}
