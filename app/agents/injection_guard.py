"""Prompt 注入检测(输入侧防线)。

策略:特征规则扫描(本地正则,<1ms),与合规审查的输出侧双阶段审核
构成"输入/输出双向"防线;命中即判定本次输入不可信,直接转人工,
不进入 Agent 决策链路。

局限(如实声明):规则法覆盖已知注入模式,复杂越狱需语义分类器——
生产演进方向是叠加轻量注入分类模型;当前规则层的取舍是零误杀成本、可解释。
"""
import re

# 注入特征:中文为主,兼顾常见英文越狱模板;忽略大小写
_PATTERNS = [
    r"忽略.{0,4}(之前|以上|上面|前面|所有|全部)?(的)?(指令|提示词?|规则|设定|约束)",
    r"(无视| disregarding?|override).{0,4}(之前|以上|上述)?(的)?(指令|规则|约束|设定)",
    r"(你现在是|你现在是新的|从现在开始你是|从现在起你(是|要 become))",
    r"(扮演|充当).{0,6}(DAN|越狱|无限制|不受限)",
    r"(系统提示词?|system\s*prompt|初始指令|开发者模式|developer\s+mode)",
    r"(输出|打印|显示|透露|告诉我).{0,8}(系统提示|初始指令|你的(设定|指令|提示词))",
    r"\b(DAN\s*mode|jailbreak)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def looks_like_injection(text: str) -> bool:
    """判定文本是否命中注入特征。短文本(确认/取消等)天然不会命中。"""
    if not text:
        return False
    trimmed = text[:500]   # 只扫前 500 字,防超长输入拖慢正则
    return any(p.search(trimmed) for p in _COMPILED)
