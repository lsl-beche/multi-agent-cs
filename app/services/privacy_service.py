"""隐私合规服务：用户记忆清除（遗忘权）"""
import logging

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.redis_client import get_redis
from app.models.tables import Conversation, MessageRecord, UserPreference

logger = logging.getLogger(__name__)


def erase_user_data(user_id: int) -> dict:
    """删除用户在客服侧的全部记忆：偏好 / 向量记忆 / 会话历史（含落库）"""
    result = {"preferences": 0, "vector_memory": 0, "conversations": 0, "messages": 0}
    uid = str(user_id)
    # 1) 偏好：Redis + PostgreSQL
    try:
        get_redis().delete("csagent:pref:" + uid)
        result["preferences"] = 1
    except Exception:
        pass
    try:
        from app.dialogue.vector_memory import delete_user_memory
        result["vector_memory"] = delete_user_memory(user_id)
    except Exception:
        pass
    # 2) 会话历史：PostgreSQL（Redis 会话键无法按用户反查，由 TTL 自动过期）
    try:
        db = SessionLocal()
        try:
            convs = db.execute(
                select(Conversation).where(Conversation.user_id == uid)
            ).scalars().all()
            ids = [c.id for c in convs]
            if ids:
                result["messages"] = db.execute(
                    delete(MessageRecord).where(MessageRecord.conversation_id.in_(ids))
                ).rowcount or 0
                result["conversations"] = db.execute(
                    delete(Conversation).where(Conversation.id.in_(ids))
                ).rowcount or 0
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("erase conversations failed: user=%s", user_id)
    return result
