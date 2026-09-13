"""安全审计：敏感操作统一落 OperationLog（脱敏后存储）。"""
import asyncio
import re
from datetime import datetime

from app.core.db import SessionLocal
from app.models.tables import OperationLog

_PHONE_RE = re.compile(r"(1\d{2})\d{4}(\d{4})")
_EMAIL_RE = re.compile(r"([A-Za-z0-9_\.\+-])[^@]+@")


def sanitize(value) -> str:
    text = str(value or "")
    text = _PHONE_RE.sub(r"\1****\2", text)
    text = _EMAIL_RE.sub(r"\1***@", text)
    return text[:1000]


def record_audit(
    *,
    user_id: int | None,
    username: str,
    module: str,
    action: str,
    target_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(OperationLog(
            user_id=user_id,
            username=username[:64],
            module=module[:32],
            action=action[:32],
            target_id=(target_id or "")[:64],
            detail={k: sanitize(v) for k, v in (detail or {}).items()},
            ip_address=ip_address,
            created_at=datetime.utcnow(),
        ))
        db.commit()
    finally:
        db.close()


async def audit_async(
    *,
    user_id: int | None,
    username: str,
    module: str,
    action: str,
    target_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        await asyncio.to_thread(
            record_audit,
            user_id=user_id,
            username=username,
            module=module,
            action=action,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
        )
    except Exception:
        # 审计失败不应阻断业务主流程，但应在上层日志中可见
        import logging
        logging.getLogger("audit").exception("audit write failed: %s/%s", module, action)
