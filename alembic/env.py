from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config.settings import settings
from app.models.tables import Base

# Alembic Config object，提供对 .ini 中值的访问
config = context.config

# 数据库 URL：优先环境变量 ALEMBIC_DATABASE_URL，否则用应用配置
db_url = os.environ.get("ALEMBIC_DATABASE_URL") or settings.postgres_url
config.set_main_option("sqlalchemy.url", db_url)

# 可选：目标 schema（用于基线生成等场景），通过 search_path 切换
_target_schema = os.environ.get("ALEMBIC_TARGET_SCHEMA")
_connect_args = {}
if _target_schema:
    _connect_args["options"] = f"-c search_path={_target_schema}"

# Python 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 使用的 metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：不创建 Engine，仅生成 SQL"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：创建 Engine 并执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 检测类型变更（如 float -> Decimal）
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
