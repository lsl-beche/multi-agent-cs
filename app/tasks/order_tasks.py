"""订单定时任务：未支付订单超时自动关闭"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config.settings import settings
from app.core.db import SessionLocal
from app.models.tables import Order
from app.services.order_service import OrderService

logger = logging.getLogger(__name__)


def close_expired_orders(now: datetime | None = None) -> int:
    """关闭超过 order_timeout_minutes 仍未支付的订单（自动释放库存）"""
    from app.core.lock import redis_lock

    try:
        with redis_lock("close_expired_orders", ttl=60):
            now = now or datetime.utcnow()
            deadline = now - timedelta(minutes=settings.order_timeout_minutes)
            db = SessionLocal()
            closed = 0
            try:
                rows = db.execute(
                    select(Order).where(
                        Order.pay_status == "unpaid",
                        Order.order_status == "pending",
                        Order.created_at < deadline,
                    )
                ).scalars().all()
                for o in rows:
                    try:
                        OrderService._transition(db, o, "cancelled", detail="超时未支付自动关闭")
                        from app.core.events import publish_sync
                        publish_sync("order.cancelled", {"order_id": o.id, "order_no": o.order_no, "reason": "timeout"})
                        closed += 1
                    except ValueError:
                        continue  # 状态不满足流转条件则跳过
                if closed:
                    logger.info("超时未支付订单自动关闭 %d 单", closed)
                return closed
            finally:
                db.close()
    except TimeoutError:
        logger.warning("close_expired_orders 锁被占用，跳过本轮")
        return 0
