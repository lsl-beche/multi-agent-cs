"""工具注册中心 / 工具市场：统一注册、发现、权限与开关

设计：每个工具模块在导入时调用 register(tool) 注册到进程级 _REGISTRY，
供以下场景使用：
1. Agent 平台管理接口：GET /api/admin/agents/tools 列出全部工具目录
2. 单元测试：验证注册完整性
3. 云端 tool-calling：工具对象带 schema（由 langchain @tool 自动生成）
4. 平台化管控：工具可禁用、标记读写权限、风险等级、聚合调用统计

注册是"副作用式"的（模块导入即注册），与 LangChain BaseTool 兼容，
新增工具只需定义 @tool 函数 + register(函数名)，无需改其他代码。
"""
from langchain_core.tools import BaseTool

_REGISTRY: dict[str, BaseTool] = {}
_ENABLED: dict[str, bool] = {}
_METADATA: dict[str, dict] = {}


def _infer_metadata(tool: BaseTool) -> dict:
    name = tool.name
    description = (tool.description or "").strip()
    if name.startswith(("propose_", "execute_", "request_", "create_", "claim_", "reply_", "take_")):
        read_only = False
        risk = "write"
    elif name.startswith(("search_", "get_", "check_", "list_", "query_")):
        read_only = True
        risk = "low"
    else:
        read_only = True
        risk = "low"
    if any(k in name or k in description for k in ("refund", "dispute", "invoice", "ticket", "address")):
        category = "交易与售后"
    elif any(k in name or k in description for k in ("product", "stock", "review", "promotion", "coupon")):
        category = "商品与营销"
    elif "logistics" in name or "shipment" in name or "track" in name:
        category = "物流"
    elif "policy" in name or "compliance" in name:
        category = "合规政策"
    else:
        category = "通用"
    return {
        "name": name,
        "description": description[:200],
        "category": category,
        "read_only": read_only,
        "risk": risk,
    }


def register(
    tool: BaseTool,
    *,
    category: str | None = None,
    read_only: bool | None = None,
    risk: str | None = None,
) -> BaseTool:
    """注册工具到全局目录（幂等：同名覆盖），并维护工具市场元数据。"""
    metadata = _infer_metadata(tool)
    if category is not None:
        metadata["category"] = category
    if read_only is not None:
        metadata["read_only"] = read_only
    if risk is not None:
        metadata["risk"] = risk
    _REGISTRY[tool.name] = tool
    _METADATA[tool.name] = metadata
    _ENABLED.setdefault(tool.name, True)
    return tool


def get_tool(name: str) -> BaseTool | None:
    """按名称取工具（不存在返回 None）"""
    return _REGISTRY.get(name)


def all_tools() -> list[BaseTool]:
    return list(_REGISTRY.values())


def is_enabled(name: str) -> bool:
    if name in _ENABLED:
        return _ENABLED[name]
    try:
        from app.core.redis_client import get_redis
        raw = get_redis().get(f"csagent:tool_enabled:{name}")
        enabled = raw not in (b"0", "0")
        _ENABLED[name] = enabled
        return enabled
    except Exception:
        return True


def set_enabled(name: str, enabled: bool) -> bool:
    if name not in _REGISTRY:
        return False
    _ENABLED[name] = bool(enabled)
    try:
        from app.core.redis_client import get_redis
        get_redis().set(f"csagent:tool_enabled:{name}", "1" if enabled else "0")
    except Exception:
        pass
    return True


def tool_metadata(name: str) -> dict:
    return dict(_METADATA.get(name) or _infer_metadata(_REGISTRY[name])) if name in _REGISTRY else {}


def tool_catalog() -> list[dict]:
    return [
        {
            **tool_metadata(name),
            "enabled": is_enabled(name),
        }
        for name in _REGISTRY
    ]
