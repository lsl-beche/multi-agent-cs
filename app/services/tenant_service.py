"""商户/租户基础服务（多商户/ISV 骨架）。"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.tables import Tenant


class TenantService:
    @staticmethod
    def ensure_default_tenant() -> Tenant:
        db = SessionLocal()
        try:
            tenant = db.execute(select(Tenant).where(Tenant.slug == "default")).scalar_one_or_none()
            if tenant is None:
                tenant = Tenant(name="默认商户", slug="default", status="active")
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
            return tenant
        finally:
            db.close()

    @staticmethod
    def list(db: Session) -> list[dict]:
        rows = db.execute(select(Tenant).order_by(Tenant.id)).scalars().all()
        return [TenantService._to_dict(r) for r in rows]

    @staticmethod
    def create(db: Session, name: str, slug: str, contact_email: str | None = None) -> dict:
        if db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none():
            raise ValueError("slug 已存在")
        t = Tenant(name=name[:128], slug=slug[:64], contact_email=contact_email, status="active")
        db.add(t)
        db.commit()
        db.refresh(t)
        return TenantService._to_dict(t)

    @staticmethod
    def update(db: Session, tenant_id: int, name: str | None = None, status: str | None = None) -> dict:
        t = db.get(Tenant, tenant_id)
        if not t:
            raise ValueError("商户不存在")
        if name is not None:
            t.name = name[:128]
        if status is not None:
            if status not in ("active", "disabled", "pending"):
                raise ValueError("status 不合法")
            t.status = status
        t.updated_at = datetime.utcnow()
        db.commit()
        return TenantService._to_dict(t)

    @staticmethod
    def _to_dict(t: Tenant) -> dict:
        return {
            "id": t.id, "name": t.name, "slug": t.slug,
            "contact_email": t.contact_email, "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
