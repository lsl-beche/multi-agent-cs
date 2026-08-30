"""内置事件消费者：指标计数与业务日志（Kafka 迁移时替换为远程消费者）"""
import logging

from app.core import metrics
from app.core.events import on

logger = logging.getLogger(__name__)


@on("order.created")
async def on_order_created(event: str, payload: dict) -> None:
    metrics.ORDERS_CREATED.inc()
    logger.info("event=order.created order_no=%s amount=%s", payload.get("order_no"), payload.get("pay_amount"))


@on("order.cancelled")
async def on_order_cancelled(event: str, payload: dict) -> None:
    metrics.ORDERS_CANCELLED.labels(reason=payload.get("reason", "unknown")).inc()
    logger.info("event=order.cancelled order_no=%s reason=%s", payload.get("order_no"), payload.get("reason"))


@on("payment.paid")
async def on_payment_paid(event: str, payload: dict) -> None:
    metrics.PAYMENTS_PAID.labels(channel=payload.get("channel", "unknown")).inc()
    logger.info("event=payment.paid order_no=%s amount=%s channel=%s",
                payload.get("order_no"), payload.get("amount"), payload.get("channel"))


@on("refund.completed")
async def on_refund_completed(event: str, payload: dict) -> None:
    metrics.REFUNDS_COMPLETED.inc()
    logger.info("event=refund.completed refund_no=%s order_no=%s", payload.get("refund_no"), payload.get("order_no"))


@on("shipment.track_refreshed")
async def on_shipment_refreshed(event: str, payload: dict) -> None:
    metrics.SHIPMENTS_REFRESHED.inc()
    logger.info("event=shipment.track_refreshed shipment_no=%s status=%s",
                payload.get("shipment_no"), payload.get("status"))
