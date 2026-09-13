"""渠道退款回调幂等处理测试"""
from unittest.mock import MagicMock

from app.api.routes.channel_payments import _apply_refunded


class _FakeRefund:
    status = "processing"
    completed_at = None
    refund_no = "RF-CALLBACK-001"
    amount = 88.0


class _FakeOrder:
    pay_status = "paid"
    order_no = "SO-CALLBACK-001"


def test_refund_callback_marks_completed_and_writes_ledger():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = None
    refund = _FakeRefund()
    order = _FakeOrder()

    assert _apply_refunded(db, refund, order, "R-RF-CALLBACK-001", 88.0, "wechat") is True
    assert refund.status == "completed"
    assert refund.completed_at is not None
    assert order.pay_status == "refunded"
    db.add.assert_called_once()
    db.commit.assert_called_once()
