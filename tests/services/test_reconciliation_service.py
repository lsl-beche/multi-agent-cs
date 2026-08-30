from datetime import datetime

from app.models.tables import Order, Payment
from app.services.reconciliation_service import reconcile


async def _seed_recon_data(async_db, consistent: bool):
    order = Order(
        order_no="REC-001",
        user_id=1,
        total_amount=100,
        pay_amount=100,
        pay_status="paid",
        order_status="confirmed",
        paid_at=datetime.utcnow(),
    )
    async_db.add(order)
    await async_db.flush()
    payment = Payment(
        payment_no="PAY-REC-001",
        order_id=order.id,
        user_id=1,
        amount=100,
        channel="sandbox",
        status="paid",
        paid_at=datetime.utcnow(),
    )
    async_db.add(payment)
    await async_db.flush()
    if not consistent:
        order.pay_status = "unpaid"
        payment.status = "pending"
    await async_db.commit()
    return order, payment


async def test_reconciliation_ok(async_db):
    await _seed_recon_data(async_db, consistent=True)
    result = await reconcile(async_db, window_hours=24)
    assert result["ok"] is True
    assert result["mismatches"] == []


async def test_reconciliation_detects_mismatch(async_db):
    await _seed_recon_data(async_db, consistent=False)
    result = await reconcile(async_db, window_hours=24)
    assert result["ok"] is False
    assert len(result["mismatches"]) >= 1

