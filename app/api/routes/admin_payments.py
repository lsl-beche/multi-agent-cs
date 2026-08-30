"""支付管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get("", summary="支付流水列表")
async def list_payments(
    user: dict = Depends(require_permission("payments", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    data, total = PaymentService.list_payments(db, page, page_size, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.get("/refunds", summary="退款列表")
async def list_refunds(
    user: dict = Depends(require_permission("payments", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    data, total = PaymentService.list_refunds(db, page, page_size, status)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/refunds/{refund_id}/approve", summary="通过退款")
async def approve_refund(refund_id: int, user: dict = Depends(require_permission("payments", "update")), db: Session = Depends(get_db)):
    try:
        result = PaymentService.approve_refund(db, refund_id, True, int(user["sub"]))
        return {"code": 0, "data": result, "message": "退款已通过"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.post("/refunds/{refund_id}/reject", summary="拒绝退款")
async def reject_refund(refund_id: int, user: dict = Depends(require_permission("payments", "update")), db: Session = Depends(get_db)):
    try:
        result = PaymentService.approve_refund(db, refund_id, False, int(user["sub"]))
        return {"code": 0, "data": result, "message": "退款已拒绝"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
