"""C 端支付路由（仅 HTTP 适配）"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import current_user, get_db
from app.models.schemas import PaymentConfirmRequest, PaymentInitiateRequest
from app.services.payment_service import PaymentService

router = APIRouter()


async def _uid(request: Request) -> int:
    payload = await current_user(request)
    return int(payload["sub"])


@router.post("/pay")
async def initiate_payment(body: PaymentInitiateRequest, request: Request, db=Depends(get_db)):
    user_id = await _uid(request)
    # 风控：支付频率/黑名单
    from app.core.risk import evaluate_async as risk_evaluate_async
    risk = await risk_evaluate_async("payment", {"user_id": user_id, "ip": request.client.host if request.client else None})
    if risk["action"] == "block":
        raise HTTPException(403, detail="支付行为异常，请稍后再试")
    try:
        result = await PaymentService.initiate_payment_async(
            db, body.order_id, user_id, body.channel
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"code": 0, "data": result}


@router.post("/confirm")
async def confirm_payment(body: PaymentConfirmRequest, request: Request, db=Depends(get_db)):
    user_id = await _uid(request)
    try:
        result = await PaymentService.confirm_payment_async(
            db,
            body.payment_no,
            user_id,
            body.signature,
            body.timestamp,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    from app.core.events import publish
    await publish("payment.paid", result)
    return {"code": 0, "data": result, "message": "支付成功"}


@router.get("/{order_id}/status")
async def payment_status(order_id: int, request: Request, db=Depends(get_db)):
    user_id = await _uid(request)
    try:
        result = await PaymentService.get_payment_status_async(db, order_id, user_id)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    return {"code": 0, "data": result}
