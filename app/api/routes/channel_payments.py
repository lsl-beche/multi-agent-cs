"""支付渠道回调：微信 APIv3 / 支付宝 异步通知（验签→幂等→入渠道账本）"""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import ChannelLedger, Order, Payment, Refund
from app.services.payment_gateway import AlipayProvider, WechatPayProvider

router = APIRouter()


def _apply_paid(db, order, payment, trade_no: str, amount: float, channel: str) -> bool:
    """幂等标记支付成功，并写入渠道账本"""
    if abs(amount - float(order.pay_amount)) > 0.01:
        # 资损防护:回调金额与订单应付不符时拒绝入账(路由层转为 400,渠道会重试核对)
        raise ValueError(f"回调金额 {amount} 与订单应付 {order.pay_amount} 不一致")
    if payment.status != "paid":
        payment.status = "paid"
        payment.paid_at = datetime.utcnow()
        payment.trade_no = trade_no or payment.trade_no
        order.pay_status = "paid"
        order.paid_at = datetime.utcnow()
        if order.order_status == "pending":
            order.order_status = "confirmed"
    ledger = db.execute(select(ChannelLedger).where(
        ChannelLedger.channel_trade_no == trade_no)).scalar_one_or_none()
    if ledger is None:
        db.add(ChannelLedger(
            ledger_date=datetime.utcnow(), channel=channel,
            type="payment", channel_trade_no=trade_no, out_no=order.order_no,
            amount=amount, status="paid", raw={},
        ))
    db.commit()
    return True


def _find(db, out_trade_no: str):
    order = db.execute(select(Order).where(Order.order_no == out_trade_no)).scalar_one_or_none()
    payment = db.execute(select(Payment).where(Payment.order_id == order.id)).scalars().first() if order else None
    return order, payment


def _apply_refunded(db, refund: Refund, order: Order, trade_no: str, amount: float, channel: str) -> bool:
    """幂等处理渠道退款回调：更新退款状态并写入渠道侧退款流水。"""
    if abs(amount - float(refund.amount)) > 0.01:
        raise ValueError(f"退款回调金额 {amount} 与退款单 {refund.amount} 不一致")
    if refund.status != "completed":
        refund.status = "completed"
        refund.completed_at = datetime.utcnow()
    order.pay_status = "refunded"
    ledger = db.execute(select(ChannelLedger).where(
        ChannelLedger.type == "refund",
        ChannelLedger.out_no == order.order_no,
        ChannelLedger.channel_trade_no == trade_no,
    )).scalars().first()
    if ledger is None:
        db.add(ChannelLedger(
            ledger_date=datetime.utcnow(), channel=channel, type="refund",
            channel_trade_no=trade_no, out_no=order.order_no,
            amount=amount, status="refunded", raw={"refund_no": refund.refund_no},
        ))
    db.commit()
    return True


@router.post("/{channel}/callback")
async def channel_callback(channel: str, request: Request):
    """微信/支付宝回调统一入口

    - wechat：Body 为 JSON，验签 header + 解密 resource
    - alipay：Body 为 form-urlencoded，按表单验签
    验签失败返回 4xx；成功且幂等返回成功（渠道要求 200/SUCCESS）。
    """
    db = SessionLocal()
    try:
        if channel == "wechat":
            body = await request.body()
            result = WechatPayProvider().verify_callback(dict(request.headers), body)
        elif channel == "alipay":
            form = dict((k, v) for k, v in (await request.form()).items())
            result = AlipayProvider().verify_callback(form)
        else:
            return JSONResponse({"code": 400, "message": "unknown channel"}, status_code=400)

        out_no, trade_no = result["out_trade_no"], result["trade_no"]

        from app.integrations.order_java import java_enabled, mark_paid_via_java
        if java_enabled() and result.get("trade_state") in ("SUCCESS", "TRADE_SUCCESS", "TRADE_FINISHED", "success"):
            # 订单域归一:状态变更经 Java API(服务端再次校验金额,双层资损防护)
            mark_paid_via_java(out_no, trade_no, float(result.get("amount", 0)))
            return JSONResponse({"code": "SUCCESS", "message": "ok"}, status_code=200)

        order, payment = _find(db, out_no)
        if not order or not payment:
            return JSONResponse({"code": 404, "message": "order not found"}, status_code=404)
        if result.get("trade_state") not in ("SUCCESS", "TRADE_SUCCESS", "TRADE_FINISHED", "success"):
            return JSONResponse({"code": 200, "message": "not success state"}, status_code=200)
        _apply_paid(db, order, payment, trade_no, float(result.get("amount", payment.amount)), channel)

        import asyncio

        from app.core.events import publish
        asyncio.get_running_loop().create_task(publish("payment.paid", {
            "order_id": order.id, "order_no": order.order_no, "payment_no": payment.payment_no,
            "amount": float(payment.amount), "channel": channel, "user_id": payment.user_id,
        }))
        return JSONResponse({"code": "SUCCESS", "message": "ok"}, status_code=200)
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": f"callback error: {type(e).__name__}"}, status_code=500)
    finally:
        db.close()


@router.post("/{channel}/refund-callback")
async def channel_refund_callback(channel: str, request: Request):
    """微信/支付宝退款异步通知：验签→识别退款单→幂等更新。"""
    db = SessionLocal()
    try:
        if channel == "wechat":
            body = await request.body()
            result = WechatPayProvider().verify_refund_callback(dict(request.headers), body)
        elif channel == "alipay":
            form = dict((k, v) for k, v in (await request.form()).items())
            result = AlipayProvider().verify_refund_callback(form)
        else:
            return JSONResponse({"code": 400, "message": "unknown channel"}, status_code=400)

        refund_no = result.get("out_refund_no", "")
        if not refund_no:
            return JSONResponse({"code": 400, "message": "refund_no missing"}, status_code=400)
        refund = db.execute(select(Refund).where(
            Refund.refund_no == refund_no)).scalar_one_or_none()
        if refund is None:
            return JSONResponse({"code": 404, "message": "refund not found"}, status_code=404)
        order = db.execute(select(Order).where(Order.id == refund.order_id)).scalar_one_or_none()
        if order is None:
            return JSONResponse({"code": 404, "message": "order not found"}, status_code=404)
        if result.get("refund_status") not in ("SUCCESS", "REFUND_SUCCESS", "success"):
            return JSONResponse({"code": 200, "message": "refund not success"}, status_code=200)

        trade_no = f"R{refund.refund_no}"
        _apply_refunded(db, refund, order, trade_no, float(result.get("amount", refund.amount)), channel)

        from app.core.events import publish
        await publish("refund.completed", {
            "refund_no": refund.refund_no,
            "order_id": order.id,
            "order_no": order.order_no,
            "amount": float(refund.amount),
            "channel": channel,
        })
        return JSONResponse({"code": "SUCCESS", "message": "ok"}, status_code=200)
    except ValueError as e:
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"code": 500, "message": f"refund callback error: {type(e).__name__}"}, status_code=500)
    finally:
        db.close()


# 兼容旧配置：渠道后台常配置 /channel-callback/{channel} 前缀
@router.post("/channel-callback/{channel}")
async def channel_callback_legacy(channel: str, request: Request):
    return await channel_callback(channel, request)


@router.post("/channel-callback/{channel}/refund")
async def channel_refund_callback_legacy(channel: str, request: Request):
    return await channel_refund_callback(channel, request)
