"""售后仲裁：C 端发起/查询 + 管理端判定"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.api.middleware.auth import require_permission
from app.core.audit import audit_async
from app.services.dispute_service import DisputeService

router = APIRouter()


async def _uid(request: Request) -> int:
    return int((await current_user(request))["sub"])


@router.post("", summary="发起仲裁（退款被拒后）")
async def create_dispute(req: dict, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        uid = await _uid(request)
        d = await db.run_sync(lambda s: DisputeService.create(
            s, uid, int(req.get("order_id", 0)), req.get("reason", ""), req.get("evidence")))
        return {"code": 0, "data": {"dispute_no": d.dispute_no, "status": d.status}, "message": "仲裁已发起"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/admin/pending", summary="待判仲裁")
async def list_pending(
    request: Request,
    user: dict = Depends(require_permission("system", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await db.run_sync(lambda s: DisputeService.list_pending(s))
    return {"code": 0, "data": data}


@router.post("/admin/{dispute_id}/resolve", summary="判定仲裁（联动退款）")
async def resolve_dispute(
    dispute_id: int,
    req: dict,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.run_sync(lambda s: DisputeService.resolve(
            s, dispute_id, bool(req.get("approved")), req.get("resolution", "")))
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="dispute", action="resolve",
            target_id=str(dispute_id), detail=result,
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result, "message": "仲裁已判定"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{dispute_no}", summary="仲裁进度")
async def get_dispute(dispute_no: str, request: Request, db: AsyncSession = Depends(get_db)):
    uid = await _uid(request)
    data = await db.run_sync(lambda s: DisputeService.get_status(s, uid, dispute_no))
    if data is None:
        raise HTTPException(404, detail="仲裁不存在")
    return {"code": 0, "data": data}
