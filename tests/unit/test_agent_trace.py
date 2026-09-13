"""Agent 平台运行 Trace 单元测试"""
from app.agents.trace import TraceStore


def test_trace_roundtrip_records_nodes_tools_and_llm():
    run_id = TraceStore.start("session-test", "user-1", "测试问题")
    TraceStore.record_node(run_id, "supervisor", "ok", 12.5, "product_consult")
    TraceStore.record_tool(run_id, "search_product", {"keyword": "龙井"}, "ok", "ok", 8.2)
    TraceStore.record_llm(run_id, "knowledge_agent", 120.4, 25, "default")
    TraceStore.finish(run_id, intent="product_consult", answer="测试回答", status="success")

    data = TraceStore.get(run_id)
    assert data is not None
    assert data["status"] == "success"
    assert data["intent"] == "product_consult"
    assert len(data["nodes"]) == 1
    assert len(data["tools"]) == 1
    assert len(data["llm_calls"]) == 1
    assert data["duration_ms"] > 0
