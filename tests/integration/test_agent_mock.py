"""Agent 链路单测：用 mock LLM 走通编排图（不依赖本地推理服务）"""
import asyncio

from langchain_core.messages import AIMessage


class FakeLLM:
    """替身 LLM：无论收到什么 prompt 都返回固定回复"""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, **kwargs):
        return AIMessage(content="模拟客服回复")

    def invoke(self, messages, **kwargs):
        return AIMessage(content="模拟客服回复")


def test_workflow_mock(monkeypatch):
    monkeypatch.setattr("app.core.llm.MetricChatOpenAI", lambda **kw: FakeLLM())
    from langchain_core.messages import HumanMessage

    from app.agents.graphs.workflow import build_workflow

    workflow = build_workflow()
    result = asyncio.run(workflow.ainvoke({
        "messages": [HumanMessage(content="你好")],
        "session_id": "mock-session",
        "user_id": "mock-user",
        "slots": {},
    }))
    # 知识类意图经过 Superviso → 子 Agent → mock LLM，最终能产出回复
    assert result["messages"][-1].content == "模拟客服回复"
