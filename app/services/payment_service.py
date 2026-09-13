"""支付服务：流水查询 + 退款审核（沙箱/微信/支付宝统一契约）"""
import asyncio
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.events.outbox import record_outbox
from app.models.tables import ChannelLedger, Order, Payment, Refund
from app.repositories import InventoryRepository, OrderRepository, PaymentRepository, RefundRepository
from app.services.async_bridge import async_adapter
from app.services.payment_gateway import get_gateway, sign_payload, verify_signature


class PaymentService:

    @staticmethod
    async def initiate_payment_async(
        db: AsyncSession,
        order_id: int,
        user_id: int,
        channel: str = "wechat",
    ) -> dict:
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise ValueError("订单不存在")
        if order.pay_status == "paid":
            raise ValueError("订单已支付")
        if order.order_status in ("cancelled", "completed"):
            raise ValueError(f"订单状态为 {order.order_status}，无法支付")
        timeout = settings.payment_expire_minutes * 60
        if order.created_at and (datetime.utcnow() - order.created_at).total_seconds() > timeout:
            raise ValueError("订单已超时，请重新下单")

        gateway = get_gateway()
        created = gateway.create_payment(order)
        # 统一真实渠道返回契约：微信 code_url / 支付宝 pay_url / 沙箱 mock_qr
        pay_url = created.get("mock_qr") or created.get("code_url") or created.get("pay_url", "")
        timestamp = created.get("timestamp") or int(time.time())
        trade_no = created.get("trade_no") or None
        payment_repo = PaymentRepository(db)
        payment = (await db.execute(
            select(Payment).where(Payment.order_id == order.id, Payment.status == "pending")
        )).scalars().first()
        if payment is None:
            payment = Payment(
                payment_no=created["payment_no"],
                order_id=order.id,
                user_id=user_id,
                amount=float(order.pay_amount),
                channel=channel,
                trade_no=trade_no,
                status="pending",
            )
            db.add(payment)
            await db.commit()
            await db.refresh(payment)
        else:
            created["payment_no"] = payment.payment_no
            trade_no = payment.trade_no
            created["trade_no"] = trade_no
            created["timestamp"] = timestamp
            created["signature"] = created.get("signature") or sign_payload({
                "payment_no": payment.payment_no,
                "trade_no": trade_no,
                "amount": float(payment.amount),
                "timestamp": timestamp,
            })
        return {
            "payment_no": created.get("payment_no") or payment.payment_no,
            "trade_no": trade_no,
            "channel": channel,
            "amount": float(order.pay_amount),
            "status": payment.status,
            "mock_qr": pay_url,
            "pay_url": pay_url,
            "code_url": created.get("code_url", ""),
            "signature": created.get("signature", ""),
            "timestamp": timestamp,
            "provider": getattr(gateway, "provider", channel),
            "message": "支付单已创建，请完成支付",
        }

    @staticmethod
    async def confirm_payment_async(db: AsyncSession, payment_no: str, user_id: int, signature: str, timestamp: int) -> dict:
        from app.services.payment_gateway import get_gateway

        payment_repo = PaymentRepository(db)
        payment = await payment_repo.get_by_no(payment_no)
        if not payment or payment.user_id != user_id:
            raise ValueError("支付单不存在")
        if payment.status == "paid":
            return {"payment_no": payment_no, "status": "paid"}
        payload = {
            "payment_no": payment.payment_no,
            "trade_no": payment.trade_no,
            "amount": float(payment.amount),
            "timestamp": timestamp,
        }
        gateway = get_gateway()
        if getattr(gateway, "provider", "") != "sandbox":
            raise ValueError("真实渠道支付需等待渠道回调确认，不能本地确认")
        if not verify_signature(payload, signature):
            raise ValueError("签名校验失败")
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(payment.order_id)
        if not order:
            raise ValueError("订单不存在")
        payment.status = "paid"
        payment.paid_at = datetime.utcnow()
        order.pay_status = "paid"
        order.paid_at = datetime.utcnow()
        if order.order_status == "pending":
            order.order_status = "confirmed"
        await record_outbox(
            db, "payment", payment.id, "payment.paid",
            {"order_id": order.id, "payment_no": payment.payment_no, "amount": float(payment.amount)},
        )
        await db.commit()
        return {"payment_no": payment_no, "status": "paid", "order_id": order.id}

    @staticmethod
    async def get_payment_status_async(db: AsyncSession, order_id: int, user_id: int) -> dict:
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise ValueError("订单不存在")
        payment_repo = PaymentRepository(db)
        payment = await payment_repo.get_last_by_order(order.id)
        return {
            "order_id": order.id,
            "order_no": order.order_no,
            "pay_status": order.pay_status,
            "order_status": order.order_status,
            "payment_no": payment.payment_no if payment else None,
            "payment_status": payment.status if payment else None,
        }

    @staticmethod
    async def approve_refund_async(db: AsyncSession, refund_id: int, approved: bool, operator_id: int | None) -> dict:
        refund_repo = RefundRepository(db)
        refund = await refund_repo.get_by_id(refund_id)
        if not refund:
            raise ValueError("退款记录不存在")
        # 仲裁场景允许把“已拒绝”的退款重新审核通过（人工判定可推翻初审）
        if refund.status not in ("pending", "processing", "rejected"):
            raise ValueError("退款当前状态不可审核")
        if approved:
            payment = (await db.execute(select(Payment).where(
                Payment.id == refund.payment_id))).scalar_one_or_none()
            order = (await db.execute(select(Order).where(
                Order.id == refund.order_id))).scalar_one_or_none()
            if not payment or not order:
                raise ValueError("退款关联的支付/订单不存在")
            gateway = get_gateway()
            # 真实渠道：异步退款到微信/支付宝；沙箱：本地模拟成功
            await asyncio.to_thread(
                gateway.refund,
                order.order_no,
                refund.refund_no,
                float(refund.amount),
                refund.reason or "",
                float(payment.amount),
            )
            refund.status = "processing"
            refund.approved_by = operator_id
            # 渠道退款流水（对账单双侧比对）
            existing = (await db.execute(select(ChannelLedger).where(
                ChannelLedger.channel_trade_no == f"R{refund.refund_no}",
            ))).scalars().first()
            if existing is None:
                db.add(ChannelLedger(
                    ledger_date=datetime.utcnow(),
                    channel=payment.channel or "sandbox",
                    type="refund",
                    channel_trade_no=f"R{refund.refund_no}",
                    out_no=order.order_no,
                    amount=float(refund.amount),
                    status="refunded",
                    raw={"source": "admin_approve", "refund_no": refund.refund_no},
                ))
        else:
            refund.status = "rejected"
        await db.commit()
        return {"id": refund.id, "status": refund.status}

    @staticmethod
    async def complete_refund_async(db: AsyncSession, refund_id: int) -> dict:
        refund_repo = RefundRepository(db)
        refund = await refund_repo.get_by_id(refund_id)
        if not refund:
            raise ValueError("退款记录不存在")
        if refund.status != "processing":
            raise ValueError("退款当前状态不能标记到账")
        refund.status = "completed"
        refund.completed_at = datetime.utcnow()
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(refund.order_id)
        if order:
            order.pay_status = "refunded"
            order_items = await order_repo.get_items(order.id)
            inv_repo = InventoryRepository(db)
            for item in order_items:
                await inv_repo.release_atomic(
                    item.sku_id, item.quantity, reason="refund_complete", ref_id=refund.refund_no
                )
            # 补齐渠道侧退款流水（若在审批时已写入则幂等跳过）
            payment = (await db.execute(select(Payment).where(
                Payment.id == refund.payment_id))).scalar_one_or_none()
            existing = (await db.execute(select(ChannelLedger).where(
                ChannelLedger.channel_trade_no == f"R{refund.refund_no}",
            ))).scalars().first()
            if existing is None:
                db.add(ChannelLedger(
                    ledger_date=datetime.utcnow(),
                    channel=payment.channel if payment else "sandbox",
                    type="refund",
                    channel_trade_no=f"R{refund.refund_no}",
                    out_no=order.order_no,
                    amount=float(refund.amount),
                    status="refunded",
                    raw={"source": "refund_complete", "refund_no": refund.refund_no},
                ))
        await record_outbox(
            db, "refund", refund.id, "refund.completed",
            {"refund_no": refund.refund_no, "order_id": refund.order_id, "amount": float(refund.amount)},
        )
        await db.commit()
        return {"id": refund.id, "status": refund.status, "refund_no": refund.refund_no}

    @staticmethod
    def list_payments(db: Session, page: int = 1, page_size: int = 20,
                      status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Payment)
        if status:
            query = query.where(Payment.status == status)
        rows, total = paginate(db, query, page, page_size, order_by=Payment.id.desc())

        result = [{
            "id": p.id, "payment_no": p.payment_no, "order_id": p.order_id,
            "amount": float(p.amount), "channel": p.channel, "trade_no": p.trade_no,
            "status": p.status,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in rows]
        return result, total

    @staticmethod
    def list_refunds(db: Session, page: int = 1, page_size: int = 20,
                     status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Refund)
        if status:
            query = query.where(Refund.status == status)
        rows, total = paginate(db, query, page, page_size, order_by=Refund.id.desc())

        result = [{
            "id": r.id, "refund_no": r.refund_no, "order_id": r.order_id,
            "amount": float(r.amount), "reason": r.reason, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
        return result, total

    @staticmethod
    def get_payment_status_by_order(db: Session, order_no: str) -> dict:
        """按订单号查询支付流水与状态"""

        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单 {order_no}"}
        rows = db.execute(
            select(Payment).where(Payment.order_id == o.id).order_by(Payment.id.desc())
        ).scalars().all()
        return {
            "order_no": order_no,
            "pay_status": o.pay_status,
            "payments": [{
                "payment_no": p.payment_no,
                "amount": float(p.amount),
                "channel": p.channel,
                "status": p.status,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            } for p in rows],
        }

    @staticmethod
    def get_refunds_by_order(db: Session, order_no: str) -> dict:
        """按订单号查询退款进度"""

        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单 {order_no}"}
        rows = db.execute(
            select(Refund).where(Refund.order_id == o.id).order_by(Refund.id.desc())
        ).scalars().all()
        return {
            "order_no": order_no,
            "refunds": [{
                "refund_no": r.refund_no,
                "amount": float(r.amount),
                "reason": r.reason,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            } for r in rows],
        }

    @staticmethod
    def approve_refund(db: Session, refund_id: int, approved: bool,
                       operator_id: int | None = None) -> dict:
        refund = db.execute(select(Refund).where(Refund.id == refund_id)).scalar_one_or_none()
        if not refund:
            raise ValueError("退款记录不存在")
        # 同步版同样允许仲裁推翻 rejected 状态
        if refund.status not in ("pending", "processing", "rejected"):
            raise ValueError(f"退款当前状态为 {refund.status}，无法审核")
        if approved:
            payment = db.execute(select(Payment).where(
                Payment.id == refund.payment_id)).scalar_one_or_none()
            order = db.execute(select(Order).where(
                Order.id == refund.order_id)).scalar_one_or_none()
            if not payment or not order:
                raise ValueError("退款关联的支付/订单不存在")
            get_gateway().refund(
                order.order_no, refund.refund_no, float(refund.amount), refund.reason or "",
                float(payment.amount),
            )
            refund.status = "processing"
            refund.approved_by = operator_id
            existing = db.execute(select(ChannelLedger).where(
                ChannelLedger.channel_trade_no == f"R{refund.refund_no}",
            )).scalars().first()
            if existing is None:
                db.add(ChannelLedger(
                    ledger_date=datetime.utcnow(),
                    channel=payment.channel or "sandbox",
                    type="refund",
                    channel_trade_no=f"R{refund.refund_no}",
                    out_no=order.order_no,
                    amount=float(refund.amount),
                    status="refunded",
                    raw={"source": "admin_approve", "refund_no": refund.refund_no},
                ))
        else:
            refund.status = "rejected"
        db.commit()
        return {"id": refund.id, "status": refund.status}

    @staticmethod
    def complete_refund(db: Session, refund_id: int) -> dict:
        """退款到账（沙箱渠道回调/财务确认）：标记完成并更新订单支付状态"""
        refund = db.execute(select(Refund).where(Refund.id == refund_id)).scalar_one_or_none()
        if not refund:
            raise ValueError("退款记录不存在")
        if refund.status != "processing":
            raise ValueError(f"退款当前状态为 {refund.status}，不能标记到账")
        refund.status = "completed"
        refund.completed_at = datetime.utcnow()
        order = db.execute(select(Order).where(Order.id == refund.order_id)).scalar_one_or_none()
        if order:
            order.pay_status = "refunded"
            payment = db.execute(select(Payment).where(
                Payment.id == refund.payment_id)).scalar_one_or_none()
            existing = db.execute(select(ChannelLedger).where(
                ChannelLedger.channel_trade_no == f"R{refund.refund_no}",
            )).scalars().first()
            if existing is None:
                db.add(ChannelLedger(
                    ledger_date=datetime.utcnow(),
                    channel=payment.channel if payment else "sandbox",
                    type="refund",
                    channel_trade_no=f"R{refund.refund_no}",
                    out_no=order.order_no,
                    amount=float(refund.amount),
                    status="refunded",
                    raw={"source": "refund_complete", "refund_no": refund.refund_no},
                ))
        db.commit()
        return {"id": refund.id, "status": refund.status, "refund_no": refund.refund_no}


PaymentService.list_payments_async = async_adapter(PaymentService.list_payments)
PaymentService.list_refunds_async = async_adapter(PaymentService.list_refunds)
