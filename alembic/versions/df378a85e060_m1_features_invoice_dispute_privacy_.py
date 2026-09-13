"""m1 features (invoice/dispute/privacy/ledger/risk)

Revision ID: df378a85e060
Revises: m1_role_permissions
Create Date: 2026-08-30 21:05:18.843788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    return any(i["name"] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_table_if_missing(table_name: str, *args, **kwargs) -> None:
    """幂等建表：0001 基线基于当前元数据 create_all，可能已创建同名表。"""
    if not _has_table(table_name):
        op.create_table(table_name, *args, **kwargs)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str],
                             unique: bool = False) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_table_if_exists(table_name: str) -> None:
    if _has_table(table_name):
        op.drop_table(table_name)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


# revision identifiers, used by Alembic.
revision: str = 'df378a85e060'
down_revision: Union[str, Sequence[str], None] = 'm1_role_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # channel ledgers（渠道对账账本）
    _create_table_if_missing('channel_ledgers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ledger_date', sa.DateTime(), nullable=False),
        sa.Column('channel', sa.String(length=16), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('channel_trade_no', sa.String(length=128), nullable=False),
        sa.Column('out_no', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_trade_no'),
    )
    _create_index_if_missing('channel_ledgers', 'ix_channel_ledgers_channel', ['channel'])
    _create_index_if_missing('channel_ledgers', 'ix_channel_ledgers_ledger_date', ['ledger_date'])
    _create_index_if_missing('channel_ledgers', 'ix_channel_ledgers_out_no', ['out_no'])

    # idempotency keys（幂等键）
    _create_table_if_missing('idempotency_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('scope', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('idempotency_keys', 'ix_idempotency_keys_key', ['key'], unique=True)
    _create_index_if_missing('idempotency_keys', 'ix_idempotency_keys_scope', ['scope'])
    _create_index_if_missing('idempotency_keys', 'ix_idempotency_keys_user_id', ['user_id'])

    # outbox events（事务事件表）
    _create_table_if_missing('outbox_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('aggregate_type', sa.String(length=64), nullable=False),
        sa.Column('aggregate_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('outbox_events', 'ix_outbox_events_aggregate_id', ['aggregate_id'])
    _create_index_if_missing('outbox_events', 'ix_outbox_events_aggregate_type', ['aggregate_type'])
    _create_index_if_missing('outbox_events', 'ix_outbox_events_created_at', ['created_at'])
    _create_index_if_missing('outbox_events', 'ix_outbox_events_event_type', ['event_type'])
    _create_index_if_missing('outbox_events', 'ix_outbox_events_status', ['status'])

    # risk blacklist（风控黑名单）
    _create_table_if_missing('risk_blacklist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('value', sa.String(length=128), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('risk_blacklist', 'ix_risk_blacklist_kind', ['kind'])
    _create_index_if_missing('risk_blacklist', 'ix_risk_blacklist_value', ['value'])

    # risk events（风控事件）
    _create_table_if_missing('risk_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scene', sa.String(length=32), nullable=False),
        sa.Column('subject', sa.String(length=64), nullable=False),
        sa.Column('subject_value', sa.String(length=128), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('risk_events', 'ix_risk_events_scene', ['scene'])
    _create_index_if_missing('risk_events', 'ix_risk_events_subject', ['subject'])

    # privacy consents（隐私授权）
    _create_table_if_missing('privacy_consents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('doc_version', sa.String(length=32), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('privacy_consents', 'ix_privacy_consents_user_id', ['user_id'])

    # invoice requests（电子发票）
    _create_table_if_missing('invoice_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('tax_no', sa.String(length=64), nullable=True),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('invoice_no', sa.String(length=64), nullable=True),
        sa.Column('file_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('invoice_requests', 'ix_invoice_requests_order_id', ['order_id'])
    _create_index_if_missing('invoice_requests', 'ix_invoice_requests_user_id', ['user_id'])

    # disputes（售后仲裁）
    _create_table_if_missing('disputes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dispute_no', sa.String(length=64), nullable=False),
        sa.Column('refund_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['refund_id'], ['refunds.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_index_if_missing('disputes', 'ix_disputes_dispute_no', ['dispute_no'], unique=True)
    _create_index_if_missing('disputes', 'ix_disputes_order_id', ['order_id'])
    _create_index_if_missing('disputes', 'ix_disputes_user_id', ['user_id'])

    # inventory.version：库存乐观锁版本列
    inventory_columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("inventory")}
    if "version" not in inventory_columns:
        op.add_column('inventory', sa.Column('version', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    inventory_columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("inventory")}
    if "version" in inventory_columns:
        op.drop_column('inventory', 'version')

    _drop_index_if_exists('disputes', 'ix_disputes_user_id')
    _drop_index_if_exists('disputes', 'ix_disputes_order_id')
    _drop_index_if_exists('disputes', 'ix_disputes_dispute_no')
    _drop_table_if_exists('disputes')

    _drop_index_if_exists('invoice_requests', 'ix_invoice_requests_user_id')
    _drop_index_if_exists('invoice_requests', 'ix_invoice_requests_order_id')
    _drop_table_if_exists('invoice_requests')

    _drop_index_if_exists('privacy_consents', 'ix_privacy_consents_user_id')
    _drop_table_if_exists('privacy_consents')

    _drop_index_if_exists('risk_events', 'ix_risk_events_subject')
    _drop_index_if_exists('risk_events', 'ix_risk_events_scene')
    _drop_table_if_exists('risk_events')

    _drop_index_if_exists('risk_blacklist', 'ix_risk_blacklist_value')
    _drop_index_if_exists('risk_blacklist', 'ix_risk_blacklist_kind')
    _drop_table_if_exists('risk_blacklist')

    _drop_index_if_exists('channel_ledgers', 'ix_channel_ledgers_out_no')
    _drop_index_if_exists('channel_ledgers', 'ix_channel_ledgers_ledger_date')
    _drop_index_if_exists('channel_ledgers', 'ix_channel_ledgers_channel')
    _drop_table_if_exists('channel_ledgers')
