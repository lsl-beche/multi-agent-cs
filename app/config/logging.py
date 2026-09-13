"""日志配置：结构化日志，对接监控采集"""
import sys

from loguru import logger

from app.api.middleware.trace import current_trace_id
from app.config.settings import settings

# 全局日志统一注入 trace_id（patch 返回新 logger，因此必须在模块导入时立即应用）
logger = logger.patch(lambda record: record["extra"].update(trace_id=current_trace_id()))


def setup_logging() -> None:
    from loguru import logger as _logger

    _logger.remove()
    _logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{extra[trace_id]}</cyan> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
    )
    _logger.add(
        "logs/csagent.log",
        rotation="50 MB",
        retention="7 days",
        level=settings.log_level,
        encoding="utf-8",
        enqueue=True,  # 多进程/异步安全
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[trace_id]} | {name}:{function}:{line} - {message}",
    )
    # perf 性能日志独立文件（供性能分析/看板采集）
    _logger.add(
        "logs/csagent_perf.log",
        rotation="50 MB",
        retention="7 days",
        level=settings.log_level,
        encoding="utf-8",
        filter=lambda record: record["name"] == "perf",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[trace_id]} | {message}",
    )


__all__ = ["logger", "setup_logging"]
