"""工单领域服务（原生异步）"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import manager
from app.models.tables import Conversation, MessageRecord, Ticket


class TicketService:
    @staticmethod
    async def _find_ticket(db: AsyncSession, ticket_id: str) -> Ticket | None:
        return (await db.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        )).scalars().first()

    @staticmethod
    async def get_or_create_conversation(db: AsyncSession, session_id: str) -> Conversation | None:
        conv = (await db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )).scalars().first()
        if not conv:
            conv = Conversation(session_id=session_id, user_id="", status="active")
            db.add(conv)
            await db.commit()
            await db.refresh(conv)
        return conv

    @staticmethod
    async def save_message(db: AsyncSession, session_id: str, role: str, content: str) -> None:
        conv = await TicketService.get_or_create_conversation(db, session_id)
        if conv:
            db.add(MessageRecord(
                conversation_id=conv.id,
                role=role,
                content=content,
                created_at=datetime.utcnow(),
            ))
            await db.commit()

    @staticmethod
    async def messages_by_session(db: AsyncSession, session_id: str) -> list[dict]:
        conv = (await db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )).scalars().first()
        if not conv:
            return []
        records = (await db.execute(
            select(MessageRecord)
            .where(MessageRecord.conversation_id == conv.id)
            .order_by(MessageRecord.created_at.asc())
        )).scalars().all()
        return [{
            "role": r.role,
            "content": r.content,
            "time": r.created_at.strftime("%H:%M") if r.created_at else "",
        } for r in records]

    @staticmethod
    def _to_dict(t: Ticket) -> dict:
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

    @staticmethod
    async def queue_status(db: AsyncSession, ticket_id: str, user_id: str) -> dict:
        t = await TicketService._find_ticket(db, ticket_id)
        if not t:
            return {"code": 404, "detail": "工单不存在"}
        if t.user_id and t.user_id != user_id:
            raise ValueError("无权访问该工单")
        if t.status != "pending":
            return {"code": 0, "data": {"position": 0, "ahead": 0, "estimated_wait_minutes": 0, "status": t.status}}
        ahead = (await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.status == "pending", Ticket.created_at < t.created_at
            )
        )).scalar() or 0
        complaint_ahead = (await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.status == "pending",
                Ticket.created_at < t.created_at,
                Ticket.category == "complaint",
            )
        )).scalar() or 0
        priority_offset = max(0, complaint_ahead - 1)
        return {
            "code": 0,
            "data": {
                "position": max(1, ahead + 1 - priority_offset),
                "ahead": ahead,
                "estimated_wait_minutes": max(1, ahead + 1 - priority_offset) * 5,
                "status": "pending",
                "created_at": t.created_at.isoformat() if t.created_at else None,
            },
        }

    @staticmethod
    async def get_ticket(db: AsyncSession, ticket_id: str, user_id: str) -> dict:
        t = await TicketService._find_ticket(db, ticket_id)
        if not t:
            return {"code": 404, "detail": "工单不存在"}
        if t.user_id and t.user_id != user_id:
            raise ValueError("无权访问该工单")
        return {"code": 0, "data": TicketService._to_dict(t)}

    @staticmethod
    async def list_tickets(db: AsyncSession, status: str | None = None) -> dict:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(100)
        if status:
            stmt = stmt.where(Ticket.status == status)
        tickets = (await db.execute(stmt)).scalars().all()
        return {"code": 0, "data": {"tickets": [TicketService._to_dict(t) for t in tickets], "total": len(tickets)}}

    @staticmethod
    async def detail(db: AsyncSession, ticket_id: str) -> dict:
        t = await TicketService._find_ticket(db, ticket_id)
        if not t:
            return {"code": 404, "detail": "工单不存在"}
        return {
            "code": 0,
            "data": {
                "ticket": TicketService._to_dict(t),
                "messages": await TicketService.messages_by_session(db, t.session_id),
                "user_online": manager.is_user_online(t.session_id),
            },
        }

    @staticmethod
    async def claim(db: AsyncSession, ticket_id: str) -> dict:
        t = await TicketService._find_ticket(db, ticket_id)
        if not t:
            return {"code": 404, "detail": "工单不存在"}
        if t.status != "pending":
            return {"code": 400, "detail": f"工单状态为 {t.status}，无法认领"}
        t.status = "claimed"
        await db.commit()
        return {"code": 0, "data": TicketService._to_dict(t)}

    @staticmethod
    async def reply(db: AsyncSession, ticket_id: str, content: str, handler: str) -> tuple[dict, str]:
        t = await TicketService._find_ticket(db, ticket_id)
        if not t:
            return {"code": 404, "detail": "工单不存在"}, ""
        await TicketService.save_message(db, t.session_id, "agent", content)
        t.status = "replied"
        await db.commit()
        return {"code": 0, "data": TicketService._to_dict(t)}, t.session_id or ""

    @staticmethod
    async def dashboard(db: AsyncSession) -> dict:
        status_rows = (await db.execute(
            select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        )).all()
        status_counts = dict(status_rows)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_count = (await db.execute(
            select(func.count(Ticket.id)).where(Ticket.created_at >= today)
        )).scalar() or 0
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
                "realtime": manager.get_stats(),
            },
        }
