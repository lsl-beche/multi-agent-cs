"""stage D/E: tenants + api_keys

Revision ID: e3c52f8f0d41
Revises: df378a85e060
Create Date: 2026-08-30 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _create_if_missing(name: str, *args, **kwargs) -> None:
    if not _has_table(name):
        op.create_table(name, *args, **kwargs)


def _index_exists(table: str, index: str) -> bool:
    return any(i["name"] == index for i in sa.inspect(op.get_bind()).get_indexes(table))


revision: str = "e3c52f8f0d41"
down_revision: Union[str, Sequence[str], None] = "df378a85e060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _create_if_missing(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("contact_email", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    _create_if_missing(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    if _has_table("tenants"):
        # 兼容基线 create_all：列可能只有 Python 默认值，DB 层补 server_default
        op.execute("ALTER TABLE tenants ALTER COLUMN created_at SET DEFAULT now()")
        op.execute("ALTER TABLE tenants ALTER COLUMN updated_at SET DEFAULT now()")
        op.execute(
            "INSERT INTO tenants (name, slug, status, created_at, updated_at) "
            "VALUES ('默认商户', 'default', 'active', now(), now()) "
            "ON CONFLICT (slug) DO NOTHING"
        )
        if not _index_exists("tenants", "ix_tenants_slug"):
            op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    if _has_table("api_keys"):
        if not _index_exists("api_keys", "ix_api_keys_tenant_id"):
            op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
        if not _index_exists("api_keys", "ix_api_keys_key_hash"):
            op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    if _has_table("api_keys"):
        op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
        op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
        op.drop_table("api_keys")
    if _has_table("tenants"):
        op.drop_table("tenants")
