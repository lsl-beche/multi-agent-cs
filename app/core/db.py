"""PostgreSQL连接：同步/异步双引擎与会话管理

- async_engine / AsyncSessionLocal：Web 请求路径优先使用
- engine / SessionLocal：脚本、worker、后台任务及旧工具兼容
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings
from app.core.metrics import PG_POOL_CHECKED_OUT, PG_POOL_CHECKS

engine = create_engine(
    settings.postgres_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,
    max_overflow=10,
    pool_timeout=10,
)

_async_url = make_url(settings.postgres_url).set(drivername="postgresql+asyncpg")

async_engine = create_async_engine(
    _async_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,
    max_overflow=10,
    pool_timeout=10,
)

# 只读副本（读写分离）：报表/看板查询走副本，主库只服务交易写路径
_reader_url = make_url(settings.pg_replica_url or settings.postgres_url).set(drivername="postgresql+asyncpg")
async_reader_engine = create_async_engine(
    _reader_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=5,
    pool_timeout=10,
)


# 连接池可观测：checkout/checkin 计数（Prometheus gauge/counter）
@event.listens_for(engine, "checkout")
def _on_checkout(dbapi_conn, conn_record, conn_proxy):
    PG_POOL_CHECKS.inc()
    PG_POOL_CHECKED_OUT.inc()


@event.listens_for(engine, "checkin")
def _on_checkin(dbapi_conn, conn_record):
    PG_POOL_CHECKED_OUT.dec()


@event.listens_for(engine, "close")
def _on_close(dbapi_conn, conn_record):
    PG_POOL_CHECKED_OUT.dec()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
)
AsyncReaderSessionLocal = async_sessionmaker(
    bind=async_reader_engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI依赖注入用的DB会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> Generator[AsyncSession, None, None]:
    """异步 FastAPI 依赖注入用的 DB 会话"""
    async with AsyncSessionLocal() as db:
        yield db


async def get_async_reader_db() -> Generator[AsyncSession, None, None]:
    """只读副本会话（报表/看板查询，配置 PG_REPLICA_URL 后自动生效）"""
    async with AsyncReaderSessionLocal() as db:
        yield db
