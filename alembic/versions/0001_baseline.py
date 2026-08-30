"""0001 基线：以当前 SQLAlchemy 元数据建全部表

后续 schema 变更请用 alembic revision --autogenerate 生成增量迁移，
保持"迁移链"可追溯、可回滚。
"""
from alembic import op

from app.core.db import Base
from app.models import tables  # noqa: F401 注册全部表

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
