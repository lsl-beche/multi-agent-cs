"""P1 测试基建：PostgreSQL / Redis 容器 fixture。

本地没有 Docker 时自动 skip，CI 中通过 testcontainers 启动真实数据库。
"""
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.models.tables import Base


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception:
        pytest.skip("Docker 不可用，跳过容器集成测试")
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    try:
        container = RedisContainer("redis:7-alpine")
        container.start()
    except Exception:
        pytest.skip("Docker 不可用，跳过 Redis 集成测试")
    yield container
    container.stop()


@pytest_asyncio.fixture(scope="session")
async def async_engine(postgres_container):
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(async_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db(async_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def redis_client(redis_container):
    import redis

    client = redis.Redis.from_url(redis_container.get_connection_url(), decode_responses=True)
    client.flushdb()
    yield client
    client.close()
