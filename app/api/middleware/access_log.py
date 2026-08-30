"""日志采集中间件：记录请求路径、状态码、耗时（对接监控体系7.1）"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.logging import logger


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        cost_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({cost_ms:.1f}ms)"
        )
        # TODO: 上报Prometheus指标（请求计数、延迟直方图 P50/P95/P99）
        return response
