"""操作日志路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.models.tables import OperationLog

router = APIRouter()


@router.get("", summary="操作日志列表")
async def list_logs(
    user: dict = Depends(require_permission("logs", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(OperationLog)
    count_query = select(func.count()).select_from(OperationLog)

    if module:
        query = query.where(OperationLog.module == module)
        count_query = count_query.where(OperationLog.module == module)
    if keyword:
        query = query.where(OperationLog.username.contains(keyword))
        count_query = count_query.where(OperationLog.username.contains(keyword))
    if start_time:
        query = query.where(OperationLog.created_at >= start_time)
        count_query = count_query.where(OperationLog.created_at >= start_time)
    if end_time:
        query = query.where(OperationLog.created_at <= end_time)
        count_query = count_query.where(OperationLog.created_at <= end_time)

    total = db.execute(count_query).scalar() or 0
    rows = db.execute(
        query.order_by(OperationLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    data = [{
        "id": r.id, "username": r.username, "module": r.module,
        "action": r.action, "target_id": r.target_id, "detail": r.detail,
        "ip_address": r.ip_address,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}
