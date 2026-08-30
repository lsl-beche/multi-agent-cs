"""对话全量落库（长期记忆之二）：PostgreSQL 持久化存档

与 Redis 会话（memory.py）的分工：
- Redis：快速读写（24h TTL、20 条），服务本轮对话
- PostgreSQL：全量存档（conversations/messages 表），供跨天恢复与审计

关键能力：
1. save_turn：每轮对话写入 2 条 MessageRecord（user + assistant）
2. load_history：Redis 过期后按 session_id 恢复（chat.py 会回填 Redis）
3. 失败兜底：任何异常只记录日志，绝不影响主对话链路
"""
import logging
from datetime import datetime

from app.core.db import SessionLocal
from app.models.tables import Conversation, MessageRecord

logger = logging.getLogger(__name__)


def _get_or_create_conversation(db, session_id: str, user_id: str) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if conv is None:
        conv = Conversation(session_id=session_id, user_id=user_id, status="active")
        db.add(conv)
        db.flush()
    return conv


def save_turn(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> bool:
    """保存一轮对话（用户消息 + 客服回复）到 PostgreSQL，失败不影响主流程

    返回 bool：成功 True；失败 False（异常已被捕获并记录日志）
    """
    if not session_id:
        return False
    try:
        db = SessionLocal()
        try:
            conv = _get_or_create_conversation(db, session_id, user_id)
            db.add(MessageRecord(conversation_id=conv.id, role="user", content=user_msg[:4000], created_at=_now()))
            db.add(MessageRecord(conversation_id=conv.id, role="assistant", content=assistant_msg[:4000], created_at=_now()))
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        logger.exception("save_turn failed: session=%s", session_id)
        return False


def _now():
    return datetime.utcnow()


def load_history(session_id: str, limit: int = 50) -> list[dict]:
    """按会话从 PostgreSQL 加载历史 [{role, content, ts}, ...]（用于跨天恢复）

    limit 默认 50 条，防止超长会话一次读太多；
    ts 为 unix 秒（与 Redis 存储格式一致，可直接回填）。
    """
    if not session_id:
        return []
    try:
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
            if conv is None:
                return []
            rows = (
                db.query(MessageRecord)
                .filter(MessageRecord.conversation_id == conv.id)
                .order_by(MessageRecord.id.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "ts": int(r.created_at.timestamp()) if r.created_at else 0,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception:
        logger.exception("load_history failed: session=%s", session_id)
        return []
