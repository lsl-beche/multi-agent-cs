"""工单 HTTP/WS 路由（业务逻辑在 TicketService）"""
import asyncio
import threading

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.api.middleware.auth import require_permission
from app.core.db import AsyncSessionLocal
from app.core.ws_manager import manager
from app.models.tables import Ticket
from app.services.ticket_service import TicketService

router = APIRouter()


async def _check_admin_ws(ws: WebSocket, required: str) -> bool:
    import jwt as jwt_lib

    from app.config.settings import settings

    token = ws.query_params.get("token", "")
    if not token:
        await ws.close(code=4001, reason="需要认证")
        return False
    try:
        payload = jwt_lib.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except Exception:
        await ws.close(code=4001, reason="认证失败")
        return False
    if payload.get("type") != "access":
        await ws.close(code=4001, reason="令牌类型错误")
        return False
    if payload.get("role") == "super_admin" or required in payload.get("permissions", []):
        return True
    await ws.close(code=4003, reason="权限不足")
    return False


@router.get("/{ticket_id}/queue-status")
async def queue_status(
    ticket_id: str,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await TicketService.queue_status(db, ticket_id, str(user.get("sub", "")))
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await TicketService.get_ticket(db, ticket_id, str(user.get("sub", "")))
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/admin/list")
async def list_tickets(
    status: str | None = None,
    user: dict = Depends(require_permission("tickets", "read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await TicketService.list_tickets(db, status)


@router.get("/admin/{ticket_id}/detail")
async def ticket_detail(
    ticket_id: str,
    user: dict = Depends(require_permission("tickets", "read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await TicketService.detail(db, ticket_id)


@router.post("/admin/{ticket_id}/claim")
async def claim_ticket(
    ticket_id: str,
    user: dict = Depends(require_permission("tickets", "update")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await TicketService.claim(db, ticket_id)


@router.post("/admin/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: str,
    content: str = Query(...),
    handler: str = Query("客服"),
    user: dict = Depends(require_permission("tickets", "update")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result, session_id = await TicketService.reply(db, ticket_id, content, handler or "客服")
    if result.get("code") == 0 and session_id:
        def _ws_push() -> None:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    manager.send_to_user(session_id, {"type": "agent", "content": content, "handler": handler})
                )
            finally:
                loop.close()

        threading.Thread(target=_ws_push, daemon=True).start()
    return result


@router.get("/admin/dashboard")
async def dashboard(
    user: dict = Depends(require_permission("tickets", "read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await TicketService.dashboard(db)


@router.websocket("/admin/ws/{ticket_id}")
async def ticket_admin_ws(ws: WebSocket, ticket_id: str) -> None:
    if not await _check_admin_ws(ws, "tickets:update"):
        return
    await ws.accept()
    async with AsyncSessionLocal() as db:
        t = (await db.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalars().first()
        if not t:
            await ws.send_json({"type": "error", "detail": "工单不存在"})
            await ws.close()
            return
        session_id = t.session_id
        await manager.connect_admin(session_id, ws)
        try:
            while True:
                data = await ws.receive_json()
                if data.get("type") == "agent_message" and data.get("content"):
                    content = data["content"]
                    handler = data.get("handler", "客服")
                    await TicketService.save_message(db, session_id, "agent", content)
                    t2 = (await db.execute(
                        select(Ticket).where(Ticket.ticket_id == ticket_id)
                    )).scalars().first()
                    if t2:
                        t2.status = "replied"
                    await db.commit()
                    await manager.send_to_user(
                        session_id,
                        {"type": "agent", "content": content, "handler": handler},
                    )
                    await ws.send_json({"type": "sent", "ok": True})
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect_admin(session_id, ws)


@router.websocket("/admin/ws/global")
async def global_admin_ws(ws: WebSocket) -> None:
    if not await _check_admin_ws(ws, "tickets:read"):
        return
    await ws.accept()
    await manager.connect_global_admin(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_global_admin(ws)
