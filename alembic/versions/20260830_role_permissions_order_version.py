"""Add role_permissions and order version column

Revision ID: 20260830_role_permissions_order_version
Revises: 0001_baseline
Create Date: 2026-08-30 17:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260830_role_permissions_order_version"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("role_id", "permission_id"),
        )

    order_columns = {c["name"] for c in inspector.get_columns("orders")}
    if "version" not in order_columns:
        op.add_column(
            "orders",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )

    inventory_columns = {c["name"] for c in inspector.get_columns("inventory")}
    if "version" not in inventory_columns:
        op.add_column(
            "inventory",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    order_columns = {c["name"] for c in inspector.get_columns("orders")}
    if "version" in order_columns:
        op.drop_column("orders", "version")
    inventory_columns = {c["name"] for c in inspector.get_columns("inventory")}
    if "version" in inventory_columns:
        op.drop_column("inventory", "version")
    op.drop_table("idempotency_keys")
    op.drop_table("outbox_events")
    if inspector.has_table("role_permissions"):
        op.drop_table("role_permissions")
