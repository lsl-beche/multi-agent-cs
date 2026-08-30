"""HTTP 指标采集中间件"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import HTTP_DURATION, HTTP_REQUESTS


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        method = request.method
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS.labels(method=method, route=route_path, status="5xx").inc()
            raise
        elapsed = time.perf_counter() - t0
        HTTP_REQUESTS.labels(method=method, route=route_path, status=str(response.status_code)).inc()
        HTTP_DURATION.labels(method=method, route=route_path).observe(elapsed)
        return response
