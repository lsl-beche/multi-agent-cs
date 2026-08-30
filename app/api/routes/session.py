"""会话管理接口：历史查询、上下文重置"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.dialogue.memory import SessionMemory
from app.models.tables import Conversation

router = APIRouter()
memory = SessionMemory()


def _ensure_owner(db: Session, session_id: str, user: dict[str, Any]) -> None:
    """校验会话归属：已绑定的会话只允许本人访问/重置"""
    conv = db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    ).scalar_one_or_none()
    if conv and conv.user_id and conv.user_id != str(user.get("sub", "")):
        raise HTTPException(status_code=403, detail="无权访问该会话")


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    user: dict[str, Any] = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_owner(db, session_id, user)
    return {"session_id": session_id, "messages": memory.load(session_id)}


@router.delete("/{session_id}")
async def reset_session(
    session_id: str,
    user: dict[str, Any] = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_owner(db, session_id, user)
    memory.clear(session_id)
    return {"session_id": session_id, "status": "cleared"}
