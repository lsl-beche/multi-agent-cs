"""Agent 平台运行追踪（Trace）

目标：把“用户一轮提问 → Supervisor → 子 Agent → 工具调用 → LLM → 回答”
落成可审计、可回放、可统计的结构化记录，供 Agent 平台页面和评测使用。

存储：
- 默认 Redis（`csagent:agent:run:<id>`，TTL 7 天 + ZSET 索引）；
- Redis 不可用时降级进程内存储（仅用于本地调试）。

字段：
- nodes：每个 LangGraph 节点的名称、状态、耗时、备注；
- tools：每次工具调用的名称、参数摘要、结果摘要、状态、耗时；
- llm_calls：每次模型调用的任务、耗时、tokens、模型分层；
- status：running / success / fallback / error；
- answer：最终客服回复摘要。

隐私：只保存用户消息摘要、工具参数摘要，不存密码、身份证、支付密码等敏感字段。
"""
import json
import time
import uuid
from collections import deque
from contextvars import ContextVar

from app.core.metrics import AGENT_TRACE_DURATION, AGENT_TRACES
from app.core.redis_client import get_redis

_PREFIX = "csagent:agent:run:"
_INDEX_KEY = "csagent:agent:runs"
_TTL = 7 * 86400
_MAX_TRACES = 5000

_current_trace_id: ContextVar[str] = ContextVar("agent_trace_id", default="")

# Redis 不可用时的进程内降级存储
_local_runs: dict[str, dict] = {}
_local_index: deque[str] = deque(maxlen=_MAX_TRACES)


def set_current_trace_id(run_id: str) -> None:
    """设置当前请求的 trace id（ContextVar，避免并发请求互相污染）。"""
    _current_trace_id.set(run_id or "")


def get_current_trace_id() -> str:
    return _current_trace_id.get()


def _redis():
    try:
        return get_redis()
    except Exception:
        return None


def _read(run_id: str) -> dict | None:
    r = _redis()
    if r is not None:
        try:
            raw = r.get(_PREFIX + run_id)
            return json.loads(raw) if raw else None
        except Exception:
            pass
    return dict(_local_runs.get(run_id) or {}) or None


def _write(run_id: str, data: dict) -> None:
    _local_runs[run_id] = data
    _local_index.append(run_id)
    r = _redis()
    if r is not None:
        try:
            r.set(_PREFIX + run_id, json.dumps(data, ensure_ascii=False), ex=_TTL)
            r.zadd(_INDEX_KEY, {run_id: data.get("started_at", time.time())})
            r.expire(_INDEX_KEY, _TTL)
            # 控制索引规模，避免 ZSET 无限增长
            count = int(r.zcard(_INDEX_KEY) or 0)
            if count > _MAX_TRACES:
                r.zremrangebyrank(_INDEX_KEY, 0, count - _MAX_TRACES - 1)
        except Exception:
            pass


def _delete(run_id: str) -> None:
    _local_runs.pop(run_id, None)
    r = _redis()
    if r is not None:
        try:
            r.delete(_PREFIX + run_id)
            r.zrem(_INDEX_KEY, run_id)
        except Exception:
            pass


class TraceStore:
    """Agent 平台 trace 存取器。"""

    @staticmethod
    def start(session_id: str, user_id: str, message: str) -> str:
        run_id = uuid.uuid4().hex[:16]
        data = {
            "run_id": run_id,
            "session_id": session_id,
            "user_id": user_id,
            "message": (message or "")[:200],
            "started_at": time.time(),
            "finished_at": None,
            "duration_ms": 0,
            "status": "running",
            "intent": "",
            "need_human": False,
            "answer": "",
            "nodes": [],
            "tools": [],
            "llm_calls": [],
            "error": "",
        }
        _write(run_id, data)
        return run_id

    @staticmethod
    def record_node(
        run_id: str,
        node: str,
        status: str = "ok",
        duration_ms: float = 0,
        remark: str = "",
    ) -> None:
        if not run_id:
            return
        data = _read(run_id)
        if data is None:
            return
        data.setdefault("nodes", []).append({
            "node": node,
            "status": status,
            "duration_ms": round(float(duration_ms), 2),
            "remark": (remark or "")[:500],
            "ts": time.time(),
        })
        _write(run_id, data)

    @staticmethod
    def record_tool(
        run_id: str,
        tool: str,
        args: dict | None = None,
        result: str = "",
        status: str = "ok",
        duration_ms: float = 0,
    ) -> None:
        if not run_id:
            return
        data = _read(run_id)
        if data is None:
            return
        args_text = json.dumps(args or {}, ensure_ascii=False, default=str)
        # 参数摘要：最多 160 字，避免把敏感完整参数写入 trace
        data.setdefault("tools", []).append({
            "tool": tool,
            "args_summary": args_text[:160],
            "result_summary": (result or "")[:200],
            "status": status,
            "duration_ms": round(float(duration_ms), 2),
            "ts": time.time(),
        })
        _write(run_id, data)

    @staticmethod
    def record_llm(
        run_id: str,
        task: str,
        duration_ms: float,
        tokens: int,
        tier: str = "default",
    ) -> None:
        if not run_id:
            return
        data = _read(run_id)
        if data is None:
            return
        data.setdefault("llm_calls", []).append({
            "task": task,
            "duration_ms": round(float(duration_ms), 2),
            "tokens": int(tokens),
            "tier": tier,
            "ts": time.time(),
        })
        _write(run_id, data)

    @staticmethod
    def finish(
        run_id: str,
        intent: str = "",
        need_human: bool = False,
        answer: str = "",
        status: str = "success",
        error: str = "",
    ) -> None:
        if not run_id:
            return
        data = _read(run_id)
        if data is None:
            return
        data["status"] = status
        data["intent"] = intent
        data["need_human"] = bool(need_human)
        data["answer"] = (answer or "")[:500]
        data["error"] = (error or "")[:500]
        data["finished_at"] = time.time()
        data["duration_ms"] = round(
            (data["finished_at"] - float(data.get("started_at") or data["finished_at"])) * 1000, 2
        )
        AGENT_TRACES.labels(status=status).inc()
        AGENT_TRACE_DURATION.labels(intent=intent or "unknown").observe(data["duration_ms"] / 1000)
        _write(run_id, data)

    @staticmethod
    def get(run_id: str) -> dict | None:
        return _read(run_id)

    @staticmethod
    def list(limit: int = 50) -> list[dict]:
        r = _redis()
        run_ids: list[str] = []
        if r is not None:
            try:
                run_ids = [
                    x.decode() if isinstance(x, bytes) else str(x)
                    for x in r.zrevrange(_INDEX_KEY, 0, limit - 1)
                ]
            except Exception:
                run_ids = []
        if not run_ids:
            run_ids = list(reversed(list(_local_index)))[:limit]
        result = []
        for run_id in run_ids:
            data = _read(run_id)
            if data:
                # 列表接口只返回概览，避免一次传输全部节点/工具细节
                result.append({
                    "run_id": run_id,
                    "session_id": data.get("session_id", ""),
                    "user_id": data.get("user_id", ""),
                    "message": data.get("message", ""),
                    "status": data.get("status", ""),
                    "intent": data.get("intent", ""),
                    "need_human": data.get("need_human", False),
                    "duration_ms": data.get("duration_ms", 0),
                    "started_at": data.get("started_at"),
                    "nodes": len(data.get("nodes", [])),
                    "tools": len(data.get("tools", [])),
                    "llm_calls": len(data.get("llm_calls", [])),
                })
        return result

    @staticmethod
    def stats() -> dict:
        traces = TraceStore.list(limit=100)
        nodes = sum(t["nodes"] for t in traces)
        tools = sum(t["tools"] for t in traces)
        llm_calls = sum(t["llm_calls"] for t in traces)
        errors = sum(1 for t in traces if t["status"] in ("error", "fallback"))
        durations = [t["duration_ms"] for t in traces if t["duration_ms"] > 0]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        p95 = 0.0
        if durations:
            ordered = sorted(durations)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        return {
            "traces": len(traces),
            "nodes": nodes,
            "tools": tools,
            "llm_calls": llm_calls,
            "llm_calls_trace": llm_calls,
            "errors": errors,
            "error_rate": round(errors / max(1, len(traces)) * 100, 2),
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": round(p95, 2),
        }


trace_store = TraceStore()
__all__ = [
    "TraceStore",
    "trace_store",
    "set_current_trace_id",
    "get_current_trace_id",
    "get_current_trace_id",
]
