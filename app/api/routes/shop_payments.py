"""C 端支付路由：发起支付（沙箱）→ 回调确认 → 状态查询（幂等闭环）"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.config.settings import settings
from app.models.tables import Order, Payment
from app.services.payment_gateway import get_gateway, sign_payload, verify_signature

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


def _get_order(db: Session, order_id: int, user_id: int) -> Order:
    order = db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "订单不存在")
    return order


@router.post("/pay")
async def initiate_payment(req: dict, request: Request, db: Session = Depends(get_db)):
    """发起支付：生成待支付单（沙箱返回模拟二维码+签名），不直接标记已支付"""
    user_id = await _uid(request)
    order_id = req.get("order_id")
    channel = req.get("channel", "wechat")
    if not order_id:
        raise HTTPException(400, "缺少订单ID")

    order = _get_order(db, int(order_id), user_id)
    if order.pay_status == "paid":
        raise HTTPException(400, "订单已支付")
    if order.order_status in ("cancelled", "completed"):
        raise HTTPException(400, f"订单状态为 {order.order_status}，无法支付")

    # 未支付订单超时检查
    timeout = settings.payment_expire_minutes * 60
    if order.created_at and (datetime.utcnow() - order.created_at).total_seconds() > timeout:
        raise HTTPException(400, "订单已超时，请重新下单")

    gateway = get_gateway()
    created = gateway.create_payment(order)

    # 幂等：同订单已有 pending 支付单则复用
    payment = db.execute(
        select(Payment).where(Payment.order_id == order.id, Payment.status == "pending")
    ).scalars().first()
    if payment is None:
        payment = Payment(
            payment_no=created["payment_no"],
            order_id=order.id,
            user_id=user_id,
            amount=float(order.pay_amount),
            channel=channel,
            trade_no=created["trade_no"],
            status="pending",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
    else:
        created["payment_no"] = payment.payment_no
        created["trade_no"] = payment.trade_no
        created["signature"] = sign_payload({
            "payment_no": payment.payment_no,
            "trade_no": payment.trade_no,
            "amount": float(payment.amount),
            "timestamp": created["timestamp"],
        })

    return {
        "code": 0,
        "data": {
            "payment_no": created["payment_no"],
            "trade_no": created["trade_no"],
            "channel": channel,
            "amount": float(order.pay_amount),
            "status": payment.status,
            "mock_qr": created["mock_qr"],
            "signature": created["signature"],
            "timestamp": created.get("timestamp", 0),
            "message": "支付单已创建，请完成支付",
        },
    }


@router.post("/confirm")
async def confirm_payment(req: dict, request: Request, db: Session = Depends(get_db)):
    """沙箱支付回调确认：校验签名 + 幂等标记已支付（生产环境由渠道回调替代）"""
    user_id = await _uid(request)
    payment_no = req.get("payment_no")
    signature = req.get("signature", "")
    if not payment_no:
        raise HTTPException(400, "缺少支付单号")

    payment = db.execute(select(Payment).where(Payment.payment_no == payment_no)).scalar_one_or_none()
    if not payment or payment.user_id != user_id:
        raise HTTPException(404, "支付单不存在")
    if payment.status == "paid":
        return {"code": 0, "data": {"payment_no": payment_no, "status": "paid"}, "message": "支付已确认"}

    # 验签（沙箱模式；生产走渠道回调验签）
    payload = {
        "payment_no": payment.payment_no,
        "trade_no": payment.trade_no,
        "amount": float(payment.amount),
        "timestamp": req.get("timestamp", 0),
    }
    if not verify_signature(payload, signature):
        raise HTTPException(400, "签名校验失败")

    order = db.get(Order, payment.order_id)
    get_gateway().confirm_payment(payment, order)
    db.commit()

    # 领域事件：支付成功
    from app.core.events import publish
    await publish("payment.paid", {
        "order_id": order.id,
        "order_no": order.order_no,
        "payment_no": payment.payment_no,
        "amount": float(payment.amount),
        "channel": payment.channel,
        "user_id": user_id,
    })

    # 行为日志：支付
    try:
        from app.models.tables import OrderItem
        from app.services.behavior_service import record
        items = db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all()
        for it in items:
            record(db, user_id, it.product_id, "pay")
    except Exception:
        pass

    return {
        "code": 0,
        "data": {
            "payment_no": payment.payment_no,
            "order_id": order.id,
            "pay_status": order.pay_status,
            "order_status": order.order_status,
            "status": "paid",
        },
        "message": "支付成功",
    }


@router.get("/{order_id}/status")
async def payment_status(order_id: int, request: Request, db: Session = Depends(get_db)):
    """查询订单支付状态"""
    user_id = await _uid(request)
    order = _get_order(db, order_id, user_id)
    payment = db.execute(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())
    ).scalars().first()
    return {
        "code": 0,
        "data": {
            "order_id": order.id,
            "order_no": order.order_no,
            "pay_status": order.pay_status,
            "order_status": order.order_status,
            "payment_no": payment.payment_no if payment else None,
            "payment_status": payment.status if payment else None,
        },
    }
