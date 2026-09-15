"""LLM客户端：统一封装大模型调用

支持两种模式（settings.llm_provider 切换）：
- local  : 本地GGUF模型（llama.cpp OpenAI兼容服务），免API Key
- 其他   : 云端API（DeepSeek/Qwen等OpenAI兼容接口），需要API Key
"""
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.core.metrics import LLM_CALLS, LLM_DURATION, LLM_TOKENS

# llama.cpp本地服务不校验Key，但OpenAI客户端要求非空
_LOCAL_DUMMY_KEY = "sk-local-no-key-required"

# 分层路由任务清单：按任务复杂度选择 fast / large / default 模型
_FAST_TASKS = {"intent", "summary", "preferences", "sentiment", "classification", "tags"}
_LARGE_TASKS = {
    "supervisor", "knowledge_agent", "order_agent", "aftersale_agent",
    "promotion_agent", "compliance_agent", "chat", "dialogue",
}


class MetricChatOpenAI(ChatOpenAI):
    """带指标采集的 ChatOpenAI：记录调用次数/耗时/估算token（按任务标签）"""

    task: str = "unknown"
    tier: str = "default"

    async def ainvoke(self, input, config=None, **kwargs):
        t0 = time.perf_counter()
        try:
            resp = await super().ainvoke(input, config=config, **kwargs)
        except Exception:
            # 主渠道失败 → 自动降级到备用渠道（须配置 LLM_FALLBACK_URL）
            resp = await self._fallback_ainvoke(input, config, kwargs)
        self._record(t0, resp)
        return resp

    def invoke(self, input, config=None, **kwargs):
        t0 = time.perf_counter()
        try:
            resp = super().invoke(input, config=config, **kwargs)
        except Exception:
            resp = self._fallback_invoke(input, config, kwargs)
        self._record(t0, resp)
        return resp

    def _fallback_client(self):
        from langchain_openai import ChatOpenAI as _ChatOpenAI
        return _ChatOpenAI(
            model=settings.llm_fallback_model or "deepseek-chat",
            api_key=settings.llm_fallback_key or "sk-no-key",
            base_url=settings.llm_fallback_url,
            temperature=settings.llm_temperature,
            max_retries=1,
            timeout=settings.llm_timeout_sec,
        )

    def _fallback_invoke(self, input, config, kwargs):
        if not settings.llm_fallback_url:
            raise
        from app.core.metrics import LLM_CALLS
        LLM_CALLS.labels(task=self.task, provider="fallback").inc()
        return self._fallback_client().invoke(input, config=config, **kwargs)

    async def _fallback_ainvoke(self, input, config, kwargs):
        if not settings.llm_fallback_url:
            raise
        from app.core.metrics import LLM_CALLS
        LLM_CALLS.labels(task=self.task, provider="fallback").inc()
        return await self._fallback_client().ainvoke(input, config=config, **kwargs)

    def _record(self, t0: float, resp) -> None:
        LLM_CALLS.labels(task=self.task, provider=settings.llm_provider).inc()
        LLM_DURATION.labels(task=self.task).observe(time.perf_counter() - t0)
        content = getattr(resp, "content", "") or ""
        tokens = max(1, len(str(content)) // 2)
        LLM_TOKENS.labels(task=self.task).inc(tokens)
        # Agent 平台 trace：把模型调用写入当前 run
        try:
            from app.agents.trace import get_current_trace_id, trace_store
            run_id = get_current_trace_id()
            if run_id:
                trace_store.record_llm(run_id, self.task, (time.perf_counter() - t0) * 1000, tokens, self.tier)
        except Exception:
            pass


def get_llm(streaming: bool = True, task: str = "unknown", **overrides) -> BaseChatModel:
    """获取LLM实例。

    Args:
        streaming: 是否流式输出（默认开启，ainvoke 调用时自动聚合，astream_events 可捕获逐token事件）
        overrides: 覆盖默认参数（如 temperature、model）
    """
    if settings.llm_provider == "local":
        params = {
            "model": settings.llm_model,  # 本地服务忽略model名，仅作标识
            "api_key": _LOCAL_DUMMY_KEY,
            "base_url": f"http://{settings.local_llm_host}:{settings.local_llm_port}/v1",
            "temperature": settings.llm_temperature,
            "streaming": streaming,
            "max_retries": 1,
            "timeout": settings.llm_timeout_sec,
            "extra_body": {
                "enable_thinking": False,  # Qwen3 禁用推理链
                "chat_template_kwargs": {"enable_thinking": False},  # 兼容旧版 llama.cpp
            },
        }
    else:
        params = {
            "model": settings.llm_model,
            "api_key": settings.llm_api_key,
            "base_url": settings.llm_base_url,
            "temperature": settings.llm_temperature,
            "streaming": streaming,
            "max_retries": 3,
            "timeout": settings.llm_timeout_sec,
        }
    params.update(overrides)
    return MetricChatOpenAI(**params, task=task)


def get_llm_for_task(task: str, **overrides):
    """按任务路由模型（规模化：意图/摘要走小模型，复杂对话走大模型）

    本地/单模型环境所有任务同一模型；云端可配置 LLM_FAST_MODEL / LLM_LARGE_MODEL。
    """
    tier = "default"
    model = settings.llm_model
    base_url = settings.llm_base_url
    api_key = settings.llm_api_key
    if settings.llm_provider != "local":
        if task in _FAST_TASKS and settings.llm_fast_model:
            tier = "fast"
            model = settings.llm_fast_model
            base_url = settings.llm_fast_base_url or settings.llm_base_url
            api_key = settings.llm_fast_api_key or settings.llm_api_key
        elif task in _LARGE_TASKS and settings.llm_large_model:
            tier = "large"
            model = settings.llm_large_model
            base_url = settings.llm_large_base_url or settings.llm_base_url
            api_key = settings.llm_large_api_key or settings.llm_api_key
    from app.core.metrics import MODEL_ROUTED
    MODEL_ROUTED.labels(task=task, tier=tier).inc()
    return get_llm(
        task=task,
        model=model,
        base_url=base_url,
        api_key=api_key,
        tier=tier,
        **overrides,
    )
