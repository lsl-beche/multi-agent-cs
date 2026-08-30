"""初始化PostgreSQL数据库：创建 csagent 数据库 + 全部27张业务表

⚠ 注意：本脚本仅供本地开发首次建库使用。
   生产环境的 schema 管理统一使用 Alembic 迁移：
       alembic upgrade head       # 应用全部迁移
       alembic revision --autogenerate -m "描述"  # 模型变更后生成迁移

前置条件：
    .env 中配置好 POSTGRES_URL（含正确的 postgres 密码）

用法：
    python scripts/init_db.py           # 仅建缺失的表（安全模式）
    python scripts/init_db.py --drop    # 先删除全部表再重建（⚠ 数据丢失）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.config.settings import settings
from app.core.db import Base, engine
from app.models import tables  # noqa: F401 导入即注册全部27张表


def ensure_database() -> None:
    """连接 postgres 维护库，创建业务数据库（如不存在）"""
    url = make_url(settings.postgres_url)
    db_name = url.database
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        ).scalar()
        if exists:
            print(f"[OK] 数据库 {db_name} 已存在")
        else:
            conn.execute(text(f'CREATE DATABASE "{db_name}" ENCODING \'UTF8\''))
            print(f"[OK] 数据库 {db_name} 创建成功")


def drop_all_tables() -> None:
    """删除所有业务表（生产环境禁用！）"""
    Base.metadata.drop_all(engine)
    print("[WARN] 已删除全部业务表")


def create_tables() -> None:
    """按 models/tables.py 定义创建全部业务表（已存在则跳过）"""
    Base.metadata.create_all(engine)
    print(f"\n[OK] 数据表初始化完成，共 {len(Base.metadata.sorted_tables)} 张表：\n")
    for table in Base.metadata.sorted_tables:
        cols = ", ".join(c.name for c in table.columns)
        print(f"  {table.name:25s}  ({cols})")


def show_table_stats() -> None:
    """显示各表的行数统计"""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    print(f"\n{'─'*60}")
    print(f"{'表名':30s} {'行数':>8s}")
    print(f"{'─'*60}")
    with engine.connect() as conn:
        for t in sorted(table_names):
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            print(f"{t:30s} {count:>8d}")
    print(f"{'─'*60}")


if __name__ == "__main__":
    drop = "--drop" in sys.argv

    ensure_database()
    if drop:
        drop_all_tables()
    create_tables()
    show_table_stats()
