"""数据报表路由：销售统计 + CS客服数据"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.auth import require_permission
from app.services.report_service import ReportService

router = APIRouter()


@router.get("/sales", summary="销售数据汇总")
async def sales_summary(
    user: dict = Depends(require_permission("reports", "read")),
    period: str = Query("today", description="today / yesterday / week / month"),
    db: AsyncSession = Depends(get_db),
):
    data = await ReportService.sales_summary_async(db, period)
    return {"code": 0, "data": data}


@router.get("/cs-agent", summary="CS客服数据大屏")
async def cs_agent_dashboard(
    user: dict = Depends(require_permission("reports", "read")),
    period: str = Query("today", description="today / week / month"),
    db: AsyncSession = Depends(get_db),
):
    data = await ReportService.cs_agent_dashboard_async(db, period)
    return {"code": 0, "data": data}
