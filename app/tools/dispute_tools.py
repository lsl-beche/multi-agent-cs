"""仲裁工具：查询进度（客服 Agent 用）"""
import json

from langchain_core.tools import tool

from app.core.db import SessionLocal
from app.services.dispute_service import DisputeService
from app.tools.registry import register


@tool
def get_dispute_status(user_id: str, dispute_no: str) -> str:
    """仲裁进度查询：按仲裁单号查询判定状态。"""
    db = SessionLocal()
    try:
        data = DisputeService.get_status(db, int(user_id), dispute_no)
        return json.dumps(data or {"error": "not_found"}, ensure_ascii=False)
    finally:
        db.close()


register(get_dispute_status)
