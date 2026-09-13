"""开放平台 / ISV 基础 API：API Key 管理 + /v1 公共接口。"""
import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.middleware.auth import require_permission
from app.core.audit import audit_async
from app.core.db import SessionLocal
from app.services.openapi_service import (
    authenticate_api_key,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)
from app.services.tenant_service import TenantService

router = APIRouter()


async def require_openapi_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> dict:
    api_key = await asyncio.to_thread(authenticate_api_key, x_api_key)
    if not api_key:
        raise HTTPException(status_code=401, detail="无效或已过期的 API Key")
    return api_key


def _tenant_list() -> list[dict]:
    db = SessionLocal()
    try:
        return TenantService.list(db)
    finally:
        db.close()


def _tenant_create(name: str, slug: str, email: str | None) -> dict:
    db = SessionLocal()
    try:
        return TenantService.create(db, name, slug, email)
    finally:
        db.close()


def _tenant_update(tenant_id: int, name: str | None, status: str | None) -> dict:
    db = SessionLocal()
    try:
        return TenantService.update(db, tenant_id, name, status)
    finally:
        db.close()


@router.get("/v1/health", summary="开放平台健康检查")
async def openapi_health():
    return {"code": 0, "data": {"service": "csagent-openapi", "status": "ok", "version": "0.2.0"}}


@router.get("/v1/tenant", summary="租户信息（需 X-API-Key）")
async def openapi_tenant(api_key: dict = Depends(require_openapi_key)):
    if "read" not in (api_key.get("scopes", {}).get("permissions") or []):
        raise HTTPException(status_code=403, detail="API Key 缺少 read 权限")
    tenant_id = api_key.get("tenant_id")
    return {"code": 0, "data": {"tenant_id": tenant_id, "name": "默认商户" if not tenant_id else "商户"}}


@router.post("/v1/chat", summary="开放平台 AI 客服（需 X-API-Key）")
async def openapi_chat(request: Request, api_key: dict = Depends(require_openapi_key)):
    if "chat" not in (api_key.get("scopes", {}).get("permissions") or []):
        raise HTTPException(status_code=403, detail="API Key 缺少 chat 权限")
    body = await request.json()
    session_id = str(body.get("session_id", "openapi"))
    message = str(body.get("message", "")).strip()
    user_id = str(body.get("user_id", "openapi"))
    if not message:
        raise HTTPException(status_code=400, detail="message 必填")
    from app.core.quota import allowed_async
    quota_ok, _, quota_limit = await allowed_async(user_id)
    if not quota_ok:
        raise HTTPException(status_code=429, detail=f"AI 对话配额已用尽（{quota_limit}）")
    from app.dialogue.chat_pipeline import run_agent
    result = await run_agent(session_id, user_id, message)
    return {"code": 0, "data": result}


@router.get("/keys", summary="API Key 列表")
async def list_keys(user: dict = Depends(require_permission("system", "read"))):
    return {"code": 0, "data": await asyncio.to_thread(list_api_keys)}


@router.post("/keys", summary="创建 API Key")
async def create_key(
    req: dict,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
):
    try:
        result = await asyncio.to_thread(
            create_api_key,
            req.get("tenant_id"),
            req.get("name", "ISV"),
            req.get("scopes", ["read"]),
            int(req.get("expires_days", 90)),
        )
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="openapi", action="key.create",
            target_id=str(result["id"]), detail={"name": result["name"]},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result, "message": "API Key 已创建，请立即保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keys/{key_id}/revoke", summary="撤销 API Key")
async def revoke_key(
    key_id: int,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
):
    ok = await asyncio.to_thread(revoke_api_key, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    await audit_async(
        user_id=int(user["sub"]), username=user["username"], module="openapi", action="key.revoke",
        target_id=str(key_id), detail={},
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "message": "API Key 已撤销"}


@router.get("/tenants", summary="商户列表")
async def list_tenants(user: dict = Depends(require_permission("system", "read"))):
    return {"code": 0, "data": await asyncio.to_thread(_tenant_list)}


@router.post("/tenants", summary="创建商户")
async def create_tenant(
    req: dict,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
):
    try:
        result = await asyncio.to_thread(
            _tenant_create,
            req.get("name", ""),
            req.get("slug", ""),
            req.get("contact_email"),
        )
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="tenant", action="create",
            target_id=str(result["id"]), detail={"slug": result["slug"]},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result, "message": "商户已创建"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/tenants/{tenant_id}", summary="更新商户")
async def update_tenant(
    tenant_id: int,
    req: dict,
    request: Request,
    user: dict = Depends(require_permission("system", "update")),
):
    try:
        result = await asyncio.to_thread(
            _tenant_update,
            tenant_id,
            req.get("name"),
            req.get("status"),
        )
        await audit_async(
            user_id=int(user["sub"]), username=user["username"], module="tenant", action="update",
            target_id=str(tenant_id), detail={"status": result.get("status")},
            ip_address=request.client.host if request.client else None,
        )
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
