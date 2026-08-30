"""Add role_permissions and order version column

Revision ID: 20260830_role_permissions_order_version
Revises: 0001_baseline
Create Date: 2026-08-30 17:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

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


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    order_columns = {c["name"] for c in inspector.get_columns("orders")}
    if "version" in order_columns:
        op.drop_column("orders", "version")
    if inspector.has_table("role_permissions"):
        op.drop_table("role_permissions")
