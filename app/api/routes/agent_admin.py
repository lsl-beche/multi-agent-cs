"""Agent 平台管理：工具目录 + 运行时性能统计"""
from fastapi import APIRouter, Depends
from prometheus_client import REGISTRY

from app.api.middleware.auth import require_permission
from app.tools.registry import all_tools

router = APIRouter()


@router.get("/tools", summary="工具目录")
async def tool_catalog(user: dict = Depends(require_permission("system", "read"))):
    """全部已注册工具（工具市场的基础清单）"""
    tools = []
    for t in all_tools():
        tools.append({
            "name": t.name,
            "description": (t.description or "")[:200],
            "args": list(getattr(t, "args", {}).keys() or []),
        })
    return {"code": 0, "data": tools, "total": len(tools)}


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
        },
    }
