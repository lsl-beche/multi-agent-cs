"""健康检查 / 就绪探针（K8s liveness & readiness）

- /health（liveness）：进程活着即 200；附带各依赖探测状态（便于排查）
- /ready（readiness）：PG/Redis 任一不可用返回 503（K8s 摘流量）；
  LLM 允许降级（规则兜底仍可用）
"""
import asyncio
import socket
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


async def _check_pg() -> dict:
    t0 = time.time()
    try:
        from app.core.db import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": type(e).__name__}


async def _check_redis() -> dict:
    t0 = time.time()
    try:
        from app.core.redis_client import get_redis
        await asyncio.to_thread(get_redis().ping)
        return {"status": "ok", "latency_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": type(e).__name__}


async def _check_llm() -> dict:
    from app.config.settings import settings
    if settings.llm_provider != "local":
        return {"status": "ok", "mode": settings.llm_provider}
    t0 = time.time()
    try:
        conn = await asyncio.to_thread(socket.create_connection, (settings.local_llm_host, settings.local_llm_port), 0.5)
        if conn:
            conn.close()
            return {"status": "ok", "latency_ms": round((time.time() - t0) * 1000)}
    except OSError:
        return {"status": "degraded", "mode": "local"}


async def _deps() -> dict:
    return {
        "postgres": await _check_pg(),
        "redis": await _check_redis(),
        "llm": await _check_llm(),
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "deps": await _deps()}


@router.get("/ready")
async def ready() -> dict:
    deps = await _deps()
    hard_ok = deps["postgres"]["status"] == "ok" and deps["redis"]["status"] == "ok"
    return JSONResponse(
        {"status": "ready" if hard_ok else "degraded", "deps": deps},
        status_code=200 if hard_ok else 503,
    )
