"""多轮对话场景回归测试

需要本地 LLM / 知识库就绪时启用；骨架阶段默认跳过。
"""
import pytest

pytestmark = pytest.mark.skip(reason="骨架阶段：需配置LLM与知识库后启用")


async def test_workflow_smoke():
    from langchain_core.messages import HumanMessage

    from app.agents.graphs.workflow import build_workflow

    workflow = build_workflow()
    result = await workflow.ainvoke(
        {
            "messages": [HumanMessage(content="我的快递到哪了")],
            "session_id": "test",
            "user_id": "tester",
            "slots": {},
        }
    )
    assert result["intent"] == "track_logistics"
    assert result.get("compliance_passed") is True
