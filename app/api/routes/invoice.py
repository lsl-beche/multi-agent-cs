"""电子发票：C 端申请/查询 + 管理端开具"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.api.middleware.auth import require_permission
from app.core.audit import audit_async
from app.services.invoice_service import InvoiceService

router = APIRouter()


async def _uid(request: Request) -> int:
    return int((await current_user(request))["sub"])


@router.post("", summary="申请发票")
async def create_invoice(req: dict, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        uid = await _uid(request)
        inv = await db.run_sync(lambda s: InvoiceService.create(
            s, uid, int(req["order_id"]), req.get("title", ""),
            req.get("tax_no", ""), req.get("email", "")))
        return {"code": 0, "data": {"id": inv.id, "order_id": inv.order_id, "status": inv.status}}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("", summary="我的发票")
async def list_invoices(request: Request, db: AsyncSession = Depends(get_db)):
    uid = await _uid(request)
    data = await db.run_sync(lambda s: InvoiceService.list_by_user(s, uid))
    return {"code": 0, "data": data}


@router.post("/admin/{inv_id}/issue", summary="管理端开具（模拟服务商）")
async def issue_invoice(
    inv_id: int,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.run_sync(lambda s: InvoiceService.issue(s, inv_id))
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="invoice", action="issue",
            target_id=str(inv_id), detail={"invoice_no": result.get("invoice_no")},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result, "message": "发票已开具"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
