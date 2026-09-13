"""风控管理：风险事件查询 + 黑名单维护"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.core.audit import audit_async
from app.models.tables import RiskBlacklist, RiskEvent

router = APIRouter()


@router.get("/events", summary="风险事件列表")
async def list_events(request: Request, scene: str | None = None,
                      limit: int = 50, user: dict = Depends(require_permission("system", "read")),
                      db=Depends(get_db)):
    q = select(RiskEvent).order_by(RiskEvent.id.desc()).limit(limit)
    if scene:
        q = q.where(RiskEvent.scene == scene)
    rows = list((await db.execute(q)).scalars().all())
    return {"code": 0, "data": [{
        "id": r.id, "scene": r.scene, "subject": r.subject, "value": r.subject_value,
        "score": r.score, "action": r.action, "detail": r.detail,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]}


@router.post("/blacklist", summary="添加黑名单")
async def add_blacklist(req: dict, request: Request, user: dict = Depends(require_permission("system", "update")),
                        db=Depends(get_db)):
    kind = req.get("kind")
    value = req.get("value")
    if kind not in ("user", "ip", "device", "phone", "address"):
        raise HTTPException(400, detail="kind 不合法")
    if not value:
        raise HTTPException(400, detail="value 必填")
    row = (await db.execute(select(RiskBlacklist).where(
        RiskBlacklist.kind == kind, RiskBlacklist.value == str(value),
    ))).scalars().first()
    if row is None:
        db.add(RiskBlacklist(kind=kind, value=str(value), reason=req.get("reason", "管理员添加")[:256]))
        await db.commit()
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="risk", action="blacklist.add",
            target_id=str(value), detail={"kind": kind, "reason": req.get("reason", "")},
            ip_address=request.client.host if request.client else None,
        )
    return {"code": 0, "message": "已加入黑名单"}
