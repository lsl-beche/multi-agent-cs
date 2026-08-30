"""工具函数单元测试"""
from app.tools.policy_tools import check_return_policy
from app.tools.registry import all_tools, get_tool


class TestToolRegistry:
    def test_policy_tool_registered(self):
        assert get_tool("check_return_policy") is not None

    def test_all_tools_not_empty(self):
        assert len(all_tools()) >= 1


class TestReturnPolicyTool:
    def test_general_policy(self):
        result = check_return_policy.invoke({"category": "general"})
        assert "退货" in result

    def test_unknown_category_fallback(self):
        result = check_return_policy.invoke({"category": "unknown"})
        assert "退货" in result  # 兜底返回通用政策
