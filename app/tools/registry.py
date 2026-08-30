"""工具注册中心：统一注册与发现 Agent 可用工具

设计：每个工具模块在导入时调用 register(tool) 注册到进程级 _REGISTRY，
供以下场景使用：
1. Agent 平台管理接口：GET /api/admin/agents/tools 列出全部工具目录
2. 单元测试：验证注册完整性
3. 云端 tool-calling：工具对象带 schema（由 langchain @tool 自动生成）

注册是"副作用式"的（模块导入即注册），与 LangChain BaseTool 兼容，
新增工具只需定义 @tool 函数 + register(函数名)，无需改其他代码。
"""
from langchain_core.tools import BaseTool

_REGISTRY: dict[str, BaseTool] = {}


def register(tool: BaseTool) -> BaseTool:
    """注册工具到全局目录（幂等：同名覆盖）"""
    _REGISTRY[tool.name] = tool
    return tool


def get_tool(name: str) -> BaseTool | None:
    """按名称取工具（不存在返回 None）"""
    return _REGISTRY.get(name)


def all_tools() -> list[BaseTool]:
    return list(_REGISTRY.values())
