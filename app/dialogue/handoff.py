"""人工转接：低置信度 / 投诉 / 主动转人工时，平滑转接人工客服

触发条件（should_handoff）：
- 意图无条件转人工：complaint（投诉）、human_service（主动转人工）
- 意图置信度低于 CONFIDENCE_THRESHOLD（0.45），说明模型"没听懂"

转接动作（transfer）：
1. 更新会话状态为 human（管理员在工单页可看到"待接管"）
2. 创建 Ticket 工单（含最近 3 轮对话摘要，客服接手前先了解语境）
3. 通过 WebSocket 实时通知所有在线管理员（global_admin_connections）

说明：transfer 在后台执行（asyncio.to_thread），不阻塞客服回复；
调用方是 workflow.human_handoff_node（转人工节点）。
"""
import logging
import secrets
from datetime import datetime

logger = logging.getLogger(__name__)


class HandoffManager:
    CONFIDENCE_THRESHOLD = 0.45  # 低于此值转人工（BGE embedding 相似度通常在 0.55-0.75 范围）
    FORCE_HANDOFF_INTENTS = {"complaint", "human_service"}  # 投诉/主动要求人工 -> 强制转接

    def should_handoff(self, intent_confidence: float, intent_name: str) -> bool:
        """判定是否需要转人工（投诉/主动转人工 强制；低置信度自动）"""
        if intent_name in self.FORCE_HANDOFF_INTENTS:
            return True
        return intent_confidence < self.CONFIDENCE_THRESHOLD

    async def transfer(self, session_id: str, reason: str, conversation_context: str = "") -> None:
        """执行转接：更新会话状态、创建工单记录、实时通知管理员

        conversation_context: 最近几轮对话摘要，供管理员快速了解用户诉求
        """
        import asyncio

        try:
            await asyncio.to_thread(self._transfer_sync, session_id, reason, conversation_context)
        except Exception:
            logger.exception("Handoff transfer failed for session=%s", session_id)

    def _transfer_sync(self, session_id: str, reason: str, conversation_context: str = "") -> None:
        """同步版本（在 to_thread 中执行），避免阻塞事件循环：
        数据库写操作 + WebSocket 通知（同步广播接口）
        """
        from app.core.db import SessionLocal
        from app.core.ws_manager import manager
        from app.models.tables import Conversation, Ticket

        with SessionLocal() as db:
            # 1) 更新会话状态为 human（标记"待人工接管"）
            conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
            if conv:
                conv.status = "human"

            # 2) 创建工单：理由（意图+问题）+ 最近对话摘要，供客服快速了解语境
            description = f"【转人工请求】\n{reason[:200]}"
            if conversation_context:
                description += f"\n\n【对话摘要】\n{conversation_context[:500]}"

            ticket = Ticket(
                ticket_id=f"TK{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}",
                session_id=session_id,
                user_id="",
                category="human_handoff",
                description=description,
                status="pending",
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            logger.info("Handoff completed: session=%s ticket=%s", session_id, ticket.ticket_id)

            # 3) 实时通知所有在线管理员（新工单事件推送）
            ticket_data = {
                "ticket_id": ticket.ticket_id,
                "session_id": ticket.session_id,
                "category": ticket.category,
                "description": ticket.description,
                "status": ticket.status,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            }
            manager.broadcast_to_global_admins_sync({
                "type": "new_ticket",
                "ticket": ticket_data,
            })
