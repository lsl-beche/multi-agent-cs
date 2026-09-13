"""Agent 平台管理：工具目录 + 运行时性能统计"""
from fastapi import APIRouter, Depends
from prometheus_client import REGISTRY

from app.agents.trace import trace_store
from app.api.middleware.auth import require_permission
from app.tools.registry import get_tool, set_enabled
from app.tools.registry import tool_catalog as registry_tool_catalog

router = APIRouter()


@router.get("/tools", summary="工具目录")
async def tool_catalog(user: dict = Depends(require_permission("system", "read"))):
    """全部已注册工具（工具市场的基础清单）"""
    tools = []
    for t in registry_tool_catalog():
        tools.append({
            **t,
            "args": list(getattr(get_tool(t["name"]), "args", {}).keys() or []),
        })
    return {"code": 0, "data": tools, "total": len(tools)}


@router.get("/traces", summary="Agent 运行 trace 列表")
async def list_traces(
    limit: int = 50,
    user: dict = Depends(require_permission("system", "read")),
):
    return {"code": 0, "data": trace_store.list(limit=min(max(limit, 1), 200))}


@router.get("/traces/{run_id}", summary="Agent 运行 trace 详情")
async def trace_detail(run_id: str, user: dict = Depends(require_permission("system", "read"))):
    data = trace_store.get(run_id)
    if data is None:
        return {"code": 404, "message": "trace 不存在"}
    return {"code": 0, "data": data}


@router.put("/tools/{name}/state", summary="启用/停用客服工具")
async def toggle_tool(
    name: str,
    payload: dict,
    user: dict = Depends(require_permission("system", "update")),
):
    enabled = bool(payload.get("enabled"))
    if not set_enabled(name, enabled):
        return {"code": 404, "message": "工具不存在"}
    return {"code": 0, "data": {"name": name, "enabled": enabled}}


def _read_metric(name: str, labels: dict | None = None) -> float:
    try:
        m = REGISTRY.get_sample_value(name, labels)
        return float(m or 0)
    except Exception:
        return 0.0


@router.get("/stats", summary="Agent 运行时统计")
async def agent_stats(user: dict = Depends(require_permission("system", "read"))):
    """从 Prometheus 指标读取：LLM/工具调用量与时延"""
    llm_total = _read_metric("csagent_llm_calls_total")
    tool_total = _read_metric("csagent_tool_calls_total")
    handoffs = _read_metric("csagent_handoffs_total")
    return {
        "code": 0,
        "data": {
            "llm_calls": llm_total,
            "tool_calls": tool_total,
            "handoffs": handoffs,
            "active_chats": _read_metric("csagent_active_chats"),
            **trace_store.stats(),
        },
    }
