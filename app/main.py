"""FastAPI 应用入口：创建app、注册中间件与路由、生命周期管理"""
import asyncio
import logging
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middleware.access_log import AccessLogMiddleware
from app.api.middleware.metrics import MetricsMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.trace import TraceMiddleware
from app.api.response import BusinessError
from app.api.routes import (
    admin_inventory,
    admin_logs,
    admin_marketing,
    admin_orders,
    admin_payments,
    admin_products,
    admin_reports,
    admin_reviews,
    admin_shipments,
    admin_users,
    agent_admin,
    auth,
    chat,
    health,
    knowledge,
    metrics,
    privacy,
    session,
    shop_cart,
    shop_coupons,
    shop_orders,
    shop_payments,
    shop_products,
    shop_reviews,
    shop_user,
    ticket,
)
from app.config.logging import setup_logging
from app.config.settings import settings
from app.config.validate import validate_security_config

logger = logging.getLogger(__name__)

# ── 本地 LLM 进程管理 ──

_llm_process: subprocess.Popen | None = None
_llm_stdout_thread: threading.Thread | None = None


def _port_listening(host: str, port: int) -> bool:
    """检查端口是否已有服务在监听"""
    import socket

    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return True
    except OSError:
        return False


def _start_local_llm() -> subprocess.Popen | None:
    """启动本地 llama.cpp 推理服务，返回子进程对象。不可用时返回 None。"""
    global _llm_stdout_thread

    if settings.llm_provider != "local":
        logger.info("LLM_PROVIDER=%s，跳过本地LLM启动", settings.llm_provider)
        return None

    # 端口已有LLM服务（独立进程管理）时直接复用，避免重复拉起和孤儿进程损坏
    if _port_listening(settings.local_llm_host, settings.local_llm_port):
        logger.info(
            "检测到 %s:%d 已有LLM服务，直接复用，跳过启动",
            settings.local_llm_host, settings.local_llm_port,
        )
        return None

    model_path = Path(settings.local_llm_model_path)
    if not model_path.exists():
        logger.warning("本地LLM模型不存在: %s，跳过启动", model_path)
        return None

    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", str(model_path),
        "--host", settings.local_llm_host,
        "--port", str(settings.local_llm_port),
        "--n_ctx", str(settings.local_llm_ctx),
        # 8逻辑核=4物理核+超线程，批量线程取4，prefill实测略快
        "--n_threads_batch", "4",
        # 服务启动级禁思考（请求级 extra_body 对此版本无效）
        "--chat_template_kwargs", '{"enable_thinking": false}',
    ]

    logger.info("正在启动本地LLM: %s (ctx=%d, port=%d)",
                model_path.name, settings.local_llm_ctx, settings.local_llm_port)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # 等待服务就绪（最多等 120 秒，逐行读取直到看到 Uvicorn running）
    deadline = time.time() + 120
    ready = False
    while time.time() < deadline and proc.stdout:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            continue
        logger.debug("[LLM] %s", line.rstrip())
        if "Uvicorn running on" in line:
            ready = True
            break

    if not ready:
        logger.error("本地LLM启动超时（120秒），请检查模型和内存")
        proc.terminate()
        return None

    # 后台线程持续消费 stdout，防止管道堵塞
    def _drain_stdout() -> None:
        try:
            while proc.stdout and proc.poll() is None:
                line = proc.stdout.readline()
                if not line:
                    break
                logger.debug("[LLM] %s", line.rstrip())
        except Exception:
            pass

    _llm_stdout_thread = threading.Thread(target=_drain_stdout, daemon=True)
    _llm_stdout_thread.start()

    logger.info("本地LLM已就绪: http://%s:%d/v1",
                 settings.local_llm_host, settings.local_llm_port)
    return proc


def _stop_local_llm(proc: subprocess.Popen | None) -> None:
    """关闭本地 LLM 子进程"""
    if proc is None:
        return
    logger.info("正在关闭本地LLM进程 (pid=%d)...", proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    logger.info("本地LLM进程已关闭")


# ── 应用生命周期 ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动/关闭时管理 LLM 进程和其他资源"""
    setup_logging()

    # 启动时：自动拉起本地 LLM
    global _llm_process
    _llm_process = _start_local_llm()

    # 预热：提前构建 Workflow 单例 + 初始化 Embedding / 向量库 / Redis
    if _llm_process is not None or settings.llm_api_key:
        logger.info("预热 Agent 工作流...")
        try:
            from app.agents.graphs.workflow import get_workflow
            _w0 = time.perf_counter()
            get_workflow()
            logger.info("Workflow 预热完成 (%.1fs)", time.perf_counter() - _w0)
        except Exception:
            logger.warning("Workflow 预热失败（不影响服务启动）")
    else:
        logger.warning("LLM 和 API Key 均不可用，跳过 Agent 预热")

    # 后台任务：未支付订单超时自动关闭（每 60 秒扫描一次）
    _task_stop = threading.Event()

    # 注册领域事件消费者（指标/日志）
    from app.core.events import register_builtin_consumers
    register_builtin_consumers()

    # Outbox 后台 worker：事务内事件最终投递
    from app.events.outbox import run_outbox_worker
    _outbox_stop = asyncio.Event()
    _outbox_task = asyncio.create_task(run_outbox_worker(interval_seconds=2, stop_event=_outbox_stop))

    async def _order_timeout_loop() -> None:
        from app.tasks.order_tasks import close_expired_orders
        while not _task_stop.is_set():
            try:
                await asyncio.to_thread(close_expired_orders)
            except Exception:
                logger.exception("close_expired_orders task failed")
            await asyncio.sleep(60)

    _order_task = asyncio.create_task(_order_timeout_loop())

    yield

    _outbox_stop.set()
    _outbox_task.cancel()
    try:
        await _outbox_task
    except (asyncio.CancelledError, Exception):
        pass

    _task_stop.set()
    _order_task.cancel()
    try:
        await _order_task
    except (asyncio.CancelledError, Exception):
        pass

    # 关闭时：释放资源
    _stop_local_llm(_llm_process)


def create_app() -> FastAPI:
    # 安全配置必须通过校验后才能构建应用，避免带空密钥启动
    validate_security_config()

    # 生产环境安全守卫：禁止使用默认密钥 / 未配置支付网关密钥
    from app.config.validation import validate_settings
    problems = validate_settings()
    if settings.app_env == "production":
        if problems:
            raise RuntimeError("生产环境配置校验未通过：\n- " + "\n- ".join(problems))
    elif problems:
        for p in problems:
            logger.warning("配置告警（开发环境不阻断）：%s", p)

    app = FastAPI(
        title="CSagent 电商智能客服",
        description="多Agent协同架构的智能客服系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 中间件（后添加的先执行）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(TraceMiddleware)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    # ── 路由 ──

    # CS Agent（原有）
    app.include_router(health.router, prefix="/api", tags=["健康检查"])
    app.include_router(metrics.router, prefix="/api", tags=["监控指标"])
    app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
    app.include_router(session.router, prefix="/api/session", tags=["会话"])
    app.include_router(ticket.router, prefix="/api/ticket", tags=["工单"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])

    # 认证
    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])

    # 管理后台
    app.include_router(admin_users.router, prefix="/api/admin/users", tags=["用户管理"])
    app.include_router(admin_products.router, prefix="/api/admin/products", tags=["商品管理"])
    app.include_router(admin_orders.router, prefix="/api/admin/orders", tags=["订单管理"])
    app.include_router(admin_inventory.router, prefix="/api/admin/inventory", tags=["库存管理"])
    app.include_router(admin_payments.router, prefix="/api/admin/payments", tags=["支付管理"])
    app.include_router(admin_shipments.router, prefix="/api/admin/shipments", tags=["物流管理"])
    app.include_router(admin_marketing.router, prefix="/api/admin/marketing", tags=["营销管理"])
    app.include_router(admin_reviews.router, prefix="/api/admin/reviews", tags=["评价管理"])
    app.include_router(admin_reports.router, prefix="/api/admin/reports", tags=["数据报表"])
    app.include_router(admin_logs.router, prefix="/api/admin/logs", tags=["操作日志"])
    app.include_router(agent_admin.router, prefix="/api/admin/agents", tags=["Agent平台"])
    app.include_router(privacy.router, prefix="/api", tags=["隐私合规"])

    # C 端商城
    app.include_router(shop_products.router, prefix="/api/products", tags=["C端商品"])
    app.include_router(shop_orders.router, prefix="/api/orders", tags=["C端订单"])
    app.include_router(shop_cart.router, prefix="/api/cart", tags=["C端购物车"])
    app.include_router(shop_user.router, prefix="/api/user", tags=["C端用户"])
    app.include_router(shop_payments.router, prefix="/api/payments", tags=["C端支付"])
    app.include_router(shop_reviews.router, tags=["C端评价"])
    app.include_router(shop_coupons.router, tags=["C端优惠券"])

    # 静态文件（商品图片等）
    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 全局异常处理：生产不泄漏堆栈/内部细节，完整审计日志
    @app.exception_handler(BusinessError)
    async def business_exception_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "data": exc.data, "message": exc.message, "detail": exc.message},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "data": None, "message": str(exc.detail), "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": 422, "data": exc.errors(), "message": "请求参数校验失败", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        from app.config.logging import logger
        logger.exception("unhandled error: %s %s", request.method, request.url.path)
        message = "服务器内部错误，请稍后再试" if settings.app_env == "production" else str(exc)
        return JSONResponse(status_code=500, content={"code": 500, "data": None, "message": message, "detail": message})

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
