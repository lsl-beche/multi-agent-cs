"""对话 HTTP/WS 路由（业务流水线在 chat_pipeline）"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.core.db import AsyncSessionLocal
from app.dialogue.chat_pipeline import chat_rate_ok, run_agent, validate_input
from app.dialogue.memory import SessionMemory
from app.models.schemas import ChatRequest, ChatResponse
from app.models.tables import Conversation, CsatScore

router = APIRouter()
memory = SessionMemory()


async def _ensure_owner(db: AsyncSession, session_id: str, user_id: str) -> bool:
    conv = (await db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    )).scalar_one_or_none()
    return not conv or not conv.user_id or conv.user_id == user_id


@router.get("/history")
async def get_chat_history(
    session_id: str,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await _ensure_owner(db, session_id, str(user.get("sub", ""))):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    history = await asyncio.to_thread(memory.load, session_id)
    if not history:
        from app.dialogue.persistence import load_history
        history = await asyncio.to_thread(load_history, session_id)
    return {"code": 0, "data": {"session_id": session_id, "messages": history}}


@router.post("/csat")
async def submit_csat(
    session_id: str,
    rating: int,
    comment: str = "",
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not 1 <= rating <= 5:
        return {"code": 400, "detail": "评分须在 1-5 之间"}
    db.add(CsatScore(
        session_id=session_id,
        user_id=str(user.get("sub", "")),
        rating=rating,
        comment=comment[:500] if comment else None,
        agent_type="ai",
    ))
    await db.commit()
    return {"code": 0, "data": {"session_id": session_id, "rating": rating}}


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    err = validate_input(req.message)
    if err:
        return ChatResponse(session_id=req.session_id, answer=err, intent="", need_human=False)
    user_id = str(user.get("sub", ""))
    if not await _ensure_owner(db, req.session_id, user_id):
        return ChatResponse(session_id=req.session_id, answer="无权访问该会话", intent="", need_human=True)
    if not chat_rate_ok(user_id):
        return ChatResponse(session_id=req.session_id, answer="消息发送过于频繁，请稍后再试。", intent="", need_human=False)
    result = await run_agent(req.session_id, user_id, req.message)
    return ChatResponse(session_id=req.session_id, **result)


async def _safe_ws_send(ws: WebSocket, data: dict) -> bool:
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


@router.websocket("/ws")
async def chat_ws(ws: WebSocket, token: str = "") -> None:
    import jwt as jwt_lib

    from app.config.settings import settings

    token_user: dict | None = None
    if token:
        try:
            token_user = jwt_lib.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            if token_user.get("type") != "access":
                await ws.close(code=4001, reason="令牌类型错误")
                return
        except Exception:
            await ws.close(code=4001, reason="认证失败")
            return
    if settings.app_env == "production" and not token:
        await ws.close(code=4001, reason="需要认证")
        return

    await ws.accept()
    current_session = None
    try:
        while True:
            data = await ws.receive_json()
            session_id = data["session_id"]
            current_session = session_id
            user_id = str(token_user.get("sub", "")) if token_user else str(data.get("user_id", ""))
            message = data["message"]

            async with AsyncSessionLocal() as db:
                if not await _ensure_owner(db, session_id, user_id):
                    await _safe_ws_send(ws, {"type": "error", "detail": "无权访问该会话"})
                    continue

            if not chat_rate_ok(user_id):
                await _safe_ws_send(ws, {"type": "error", "detail": "消息发送过于频繁，请稍后再试。"})
                continue
            err = validate_input(message)
            if err:
                await _safe_ws_send(ws, {"type": "error", "detail": err})
                continue
            result = await run_agent(session_id, user_id, message)
            await _safe_ws_send(ws, {"type": "chunk", "content": result["answer"]})
            await _safe_ws_send(ws, {"type": "done", "intent": result.get("intent", ""), "need_human": result.get("need_human", False)})
    except WebSocketDisconnect:
        pass
    finally:
        if current_session:
            from app.core.ws_manager import manager
            manager.disconnect_user(current_session)
