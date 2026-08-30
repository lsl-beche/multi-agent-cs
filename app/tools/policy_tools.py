"""政策相关工具：退换货政策查询

说明：当前是内置示例政策（骨架期占位），
正式环境应从配置中心/知识库读取，保持与售后 Agent 的提示词一致。
"""
from langchain_core.tools import tool

from app.tools.registry import register

# 骨架期内置示例政策；正式环境应从知识库/配置中心读取
_RETURN_POLICIES = {
    "general": "支持7天无理由退货（商品需保持完好、不影响二次销售）；15天内质量问题可换货；运费险覆盖的订单退货免运费。",
    "food": "食品类商品不支持7天无理由退货；质量问题可无条件退换，运费由商家承担。",
    "digital": "数码产品支持7天无理由退货（需未激活）；激活后仅支持质量问题换货。",
}


@tool
def check_return_policy(category: str = "general") -> str:
    """退换货政策查询：按商品类目查询退货/换货规则。参数 category 为类目，如 general/food/digital。"""
    return _RETURN_POLICIES.get(category, _RETURN_POLICIES["general"])


register(check_return_policy)
