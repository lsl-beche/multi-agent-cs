"""PostgreSQL连接：SQLAlchemy引擎与会话管理"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
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


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI依赖注入用的DB会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
