"""日志配置：结构化日志，对接监控采集"""
import sys

from loguru import logger

from app.config.settings import settings


def setup_logging() -> None:
    from loguru import logger as _logger

    from app.api.middleware.trace import current_trace_id

    _logger.remove()
    # 日志记录注入 trace_id（全链路可观测）
    _logger = _logger.patch(lambda record: record["extra"].update(trace_id=current_trace_id()))
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
