"""操作日志路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.models.tables import OperationLog
from app.repositories import BaseRepository

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
    db: AsyncSession = Depends(get_db),
):
    query = select(OperationLog)

    if module:
        query = query.where(OperationLog.module == module)
    if keyword:
        query = query.where(OperationLog.username.contains(keyword))
    if start_time:
        query = query.where(OperationLog.created_at >= start_time)
    if end_time:
        query = query.where(OperationLog.created_at <= end_time)

    rows, total = await BaseRepository(db).paginate(
        query, page, page_size, order_by=OperationLog.id.desc()
    )

    data = [{
        "id": r.id, "username": r.username, "module": r.module,
        "action": r.action, "target_id": r.target_id, "detail": r.detail,
        "ip_address": r.ip_address,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}
