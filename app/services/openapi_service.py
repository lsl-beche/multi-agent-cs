"""开放平台 API Key 服务：创建/鉴权/撤销（ISV 基础）。"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config.settings import settings
from app.core.db import SessionLocal
from app.models.tables import ApiKey, Tenant


def _secret() -> str:
    return settings.api_secret_key or "stage-de-dev-secret"


def key_hash(raw: str) -> str:
    return hmac.new(_secret().encode(), raw.encode(), hashlib.sha256).hexdigest()


def create_api_key(tenant_id: int | None, name: str, scopes: list[str] | None = None,
                   expires_days: int = 90) -> dict:
    db = SessionLocal()
    try:
        tenant = None
        if tenant_id:
            tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
            if not tenant:
                raise ValueError("商户不存在")
        raw = "sk_" + secrets.token_urlsafe(32)
        key = ApiKey(
            tenant_id=tenant.id if tenant else None,
            name=name[:128],
            key_hash=key_hash(raw),
            scopes={"permissions": scopes or ["read"]},
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return {
            "id": key.id, "name": key.name, "tenant_id": key.tenant_id,
            "status": key.status, "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "scopes": key.scopes,
            "api_key": raw,  # 仅创建时返回一次
        }
    finally:
        db.close()


def authenticate_api_key(raw: str) -> dict | None:
    if not raw or not raw.startswith("sk_"):
        return None
    db = SessionLocal()
    try:
        row = db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash(raw))).scalar_one_or_none()
        if not row or row.status != "active":
            return None
        if row.expires_at and row.expires_at < datetime.utcnow():
            return None
        row.last_used_at = datetime.utcnow()
        db.commit()
        return {
            "id": row.id, "name": row.name, "tenant_id": row.tenant_id,
            "scopes": row.scopes or {}, "status": row.status,
        }
    finally:
        db.close()


def list_api_keys() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.execute(select(ApiKey).order_by(ApiKey.id.desc())).scalars().all()
        return [{
            "id": r.id, "name": r.name, "tenant_id": r.tenant_id,
            "status": r.status, "scopes": r.scopes,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
    finally:
        db.close()


def revoke_api_key(key_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.get(ApiKey, key_id)
        if not row:
            return False
        row.status = "revoked"
        db.commit()
        return True
    finally:
        db.close()
