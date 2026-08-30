"""工单接口：创建 → 领取 → 回复（人工客服闭环）"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.api.deps import current_user
from app.api.middleware.auth import require_permission
from app.core.db import SessionLocal
from app.core.ws_manager import manager
from app.models.tables import Conversation, MessageRecord, Ticket

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 辅助函数 ──

def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_conversation(db, session_id: str) -> Conversation | None:
    """按 session_id 查找或创建会话记录，返回其 Conversation 对象"""
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conv:
        conv = Conversation(session_id=session_id, user_id="", status="active")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_message(db, session_id: str, role: str, content: str) -> None:
    """保存一条消息到 messages 表"""
    conv = _get_or_create_conversation(db, session_id)
    if conv:
        msg = MessageRecord(
            conversation_id=conv.id,
            role=role,
            content=content,
            created_at=datetime.utcnow(),
        )
        db.add(msg)
        db.commit()


def _ticket_to_dict(t: Ticket) -> dict:
    return {
        "ticket_id": t.ticket_id,
        "session_id": t.session_id,
        "user_id": t.user_id,
        "category": t.category,
        "description": t.description,
        "status": t.status,
        "handler": getattr(t, "handler", ""),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _get_messages_by_session(db, session_id: str) -> list[dict]:
    """按 session_id 拉取历史消息"""
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conv:
        return []
    records = (
        db.query(MessageRecord)
        .filter(MessageRecord.conversation_id == conv.id)
        .order_by(MessageRecord.created_at.asc())
        .all()
    )
    return [
        {
            "role": r.role,
            "content": r.content,
            "time": r.created_at.strftime("%H:%M") if r.created_at else "",
        }
        for r in records
    ]


async def _check_admin_ws(ws: WebSocket, required: str) -> bool:
    """WebSocket 管理员鉴权：token 必须有效且具备指定权限"""
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


# ── 公开接口 ──

@router.get("/{ticket_id}/queue-status")
def queue_status(ticket_id: str, user: dict = Depends(current_user)) -> dict:
    """查询排队状态：位置 + 预计等待时间"""
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        return {"code": 404, "detail": "工单不存在"}
    if t.user_id and t.user_id != str(user.get("sub", "")):
        raise HTTPException(status_code=403, detail="无权访问该工单")

    if t.status != "pending":
        # 已被认领或关闭，不在队列中
        return {"code": 0, "data": {"position": 0, "ahead": 0, "estimated_wait_minutes": 0, "status": t.status}}

    # FIFO: 统计在此工单之前创建的 pending 工单数
    ahead = db.query(Ticket).filter(
        Ticket.status == "pending",
        Ticket.created_at < t.created_at,
    ).count()

    # 投诉类优先：排在投诉工单之后
    complaint_ahead = db.query(Ticket).filter(
        Ticket.status == "pending",
        Ticket.created_at < t.created_at,
        Ticket.category == "complaint",
    ).count()
    priority_offset = max(0, complaint_ahead - 1)

    position = max(1, ahead + 1 - priority_offset)

    # 预估等待：假设平均每工单 5 分钟处理时间
    estimated_wait_minutes = position * 5

    return {
        "code": 0,
        "data": {
            "position": position,
            "ahead": ahead,
            "estimated_wait_minutes": estimated_wait_minutes,
            "status": "pending",
            "created_at": t.created_at.isoformat() if t.created_at else None,
        },
    }


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, user: dict = Depends(current_user)) -> dict:
    """查询工单状态（C端用户查看）"""
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        return {"code": 404, "detail": "工单不存在"}
    if t.user_id and t.user_id != str(user.get("sub", "")):
        raise HTTPException(status_code=403, detail="无权访问该工单")
    return {"code": 0, "data": _ticket_to_dict(t)}


# ── 管理后台接口 ──

@router.get("/admin/list")
def list_tickets(
    status: str | None = None,
    user: dict = Depends(require_permission("tickets", "read")),
) -> dict:
    """管理员查看工单列表（按状态过滤：pending/replied/closed）"""
    db = next(_get_db())
    q = db.query(Ticket)
    if status:
        q = q.filter(Ticket.status == status)
    q = q.order_by(Ticket.created_at.desc()).limit(100)
    tickets = [_ticket_to_dict(t) for t in q.all()]
    return {"code": 0, "data": {"tickets": tickets, "total": len(tickets)}}


@router.get("/admin/{ticket_id}/detail")
def ticket_detail(ticket_id: str, user: dict = Depends(require_permission("tickets", "read"))) -> dict:
    """工单详情（含对话历史）"""
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        return {"code": 404, "detail": "工单不存在"}

    return {
        "code": 0,
        "data": {
            "ticket": _ticket_to_dict(t),
            "messages": _get_messages_by_session(db, t.session_id),
            "user_online": manager.is_user_online(t.session_id),
        },
    }


@router.post("/admin/{ticket_id}/claim")
def claim_ticket(ticket_id: str, user: dict = Depends(require_permission("tickets", "update"))) -> dict:
    """管理员领取/认领工单"""
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        return {"code": 404, "detail": "工单不存在"}
    if t.status != "pending":
        return {"code": 400, "detail": f"工单状态为 {t.status}，无法认领"}
    t.status = "claimed"
    db.commit()
    return {"code": 0, "data": _ticket_to_dict(t)}


@router.post("/admin/{ticket_id}/reply")
def reply_ticket(
    ticket_id: str,
    content: str = Query(...),
    handler: str = Query("客服"),
    user: dict = Depends(require_permission("tickets", "update")),
) -> dict:
    """管理员回复工单：写入 DB + 通过 WebSocket 推送给用户"""
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        return {"code": 404, "detail": "工单不存在"}

    # 1) 保存管理员消息到 messages 表
    _save_message(db, t.session_id, "agent", content)

    # 2) 更新工单状态
    t.status = "replied"
    ticket_data = _ticket_to_dict(t)
    db.commit()

    # 3) 通过 WebSocket 实时推送给用户
    if t.session_id:
        import threading
        tgt_session = t.session_id
        tgt_content = content
        tgt_handler = handler or "客服"

        def _ws_push() -> None:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    manager.send_to_user(tgt_session, {"type": "agent", "content": tgt_content, "handler": tgt_handler})
                )
            finally:
                loop.close()

        threading.Thread(target=_ws_push, daemon=True).start()
        logger.info("Agent replied to session=%s", t.session_id)

    return {"code": 0, "data": ticket_data}


# ── WebSocket：管理员实时对话通道 ──

@router.websocket("/admin/ws/{ticket_id}")
async def ticket_admin_ws(ws: WebSocket, ticket_id: str) -> None:
    """管理员 WebSocket 通道：监听工单，接收用户新消息，下发回复"""
    if not await _check_admin_ws(ws, "tickets:update"):
        return
    await ws.accept()

    # 获取 session_id
    db = next(_get_db())
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        await ws.send_json({"type": "error", "detail": "工单不存在"})
        await ws.close()
        return

    session_id = t.session_id
    await manager.connect_admin(session_id, ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")
            content = data.get("content", "")
            handler = data.get("handler", "客服")

            if msg_type == "agent_message" and content:
                # 1) 保存管理员消息到 messages 表
                db2 = next(_get_db())
                _save_message(db2, session_id, "agent", content)

                # 2) 更新工单状态
                t2 = db2.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
                if t2:
                    t2.status = "replied"
                db2.commit()

                # 3) 推送给用户
                sent = await manager.send_to_user(
                    session_id,
                    {"type": "agent", "content": content, "handler": handler},
                )
                await ws.send_json({"type": "sent", "ok": sent})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_admin(session_id, ws)


@router.websocket("/admin/ws/global")
async def global_admin_ws(ws: WebSocket) -> None:
    """管理员全局通知频道：接收新工单、在线状态等系统通知"""
    if not await _check_admin_ws(ws, "tickets:read"):
        return
    await ws.accept()
    await manager.connect_global_admin(ws)
    try:
        while True:
            # 保持心跳
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_global_admin(ws)


@router.get("/admin/dashboard")
def dashboard(user: dict = Depends(require_permission("tickets", "read"))) -> dict:
    """客服监控看板：实时统计数据"""
    db = next(_get_db())

    # 工单按状态统计
    from sqlalchemy import func
    status_counts = dict(
        db.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )

    # 今日工单
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_count = db.query(Ticket).filter(
        Ticket.created_at >= today
    ).count()

    # 实时连接
    stats = manager.get_stats()

    return {
        "code": 0,
        "data": {
            "tickets": {
                "pending": status_counts.get("pending", 0),
                "claimed": status_counts.get("claimed", 0),
                "replied": status_counts.get("replied", 0),
                "closed": status_counts.get("closed", 0),
                "total": sum(status_counts.values()),
                "today": today_count,
            },
            "realtime": stats,
        },
    }
