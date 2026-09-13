"""隐私合规接口：政策说明 / 同意记录 / 遗忘权指引"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.config.settings import settings
from app.models.tables import PrivacyConsent

router = APIRouter()
PRIVACY_VERSION = "2026-08-30"


@router.get("/privacy", summary="隐私合规说明")
async def privacy() -> dict:
    """返回当前隐私政策版本、配置与遗忘权入口"""
    return {
        "code": 0,
        "data": {
            "policy_version": PRIVACY_VERSION,
            "memory_enabled": settings.user_memory_enabled,
            "memory_ttl_days": settings.memory_ttl_days,
            "erase_endpoint": "DELETE /api/user/memory（需登录）",
            "policy": "仅存储客服对话所必需的信息（偏好/会话/向量记忆），"
                      "不采集身份证、支付密码等敏感信息；可随时一键清除。",
        },
    }


@router.post("/privacy/consent", summary="记录隐私授权")
async def record_consent(request: Request, db: AsyncSession = Depends(get_db)):
    """记录用户对隐私政策的同意（注册/首次使用客服时调用）"""
    payload = await current_user(request)
    existing = (await db.execute(select(PrivacyConsent).where(
        PrivacyConsent.user_id == int(payload["sub"]),
        PrivacyConsent.doc_version == PRIVACY_VERSION,
    ).limit(1))).scalars().first()
    if existing is None:
        db.add(PrivacyConsent(
            user_id=int(payload["sub"]), doc_version=PRIVACY_VERSION, granted=True,
            source="privacy_page", ip=request.client.host if request.client else None,
        ))
        await db.commit()
    return {"code": 0, "data": {"version": PRIVACY_VERSION, "granted": True}, "message": "已记录授权"}


@router.get("/privacy/consent", summary="查询授权记录")
async def get_consent(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await current_user(request)
    row = (await db.execute(select(PrivacyConsent).where(
        PrivacyConsent.user_id == int(payload["sub"]),
        PrivacyConsent.doc_version == PRIVACY_VERSION,
    ).order_by(PrivacyConsent.id.desc()).limit(1))).scalars().first()
    return {"code": 0, "data": {
        "version": PRIVACY_VERSION, "granted": bool(row),
        "source": row.source if row else None,
        "created_at": row.created_at.isoformat() if row else None,
    }}
