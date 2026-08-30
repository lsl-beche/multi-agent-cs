"""知识库管理接口：条目增删、检索测试、热更新Webhook"""
import hashlib
import hmac
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import current_user
from app.config.settings import settings
from app.knowledge.updater import KnowledgeUpdater
from app.models.schemas import KnowledgeItem

router = APIRouter()
updater = KnowledgeUpdater()

WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5分钟时间戳容差


@router.post("/items")
async def add_items(items: list[KnowledgeItem], user: dict[str, Any] = Depends(current_user)) -> dict:
    count = updater.upsert([item.model_dump() for item in items])
    return {"added": count}


@router.get("/search")
async def search(q: str, top_k: int = 5, user: dict[str, Any] = Depends(current_user)) -> dict:
    from app.knowledge.retriever import KnowledgeRetriever

    docs = KnowledgeRetriever(top_k=top_k).retrieve(q)
    return {"query": q, "results": [{"content": d.page_content, "metadata": d.metadata} for d in docs]}


@router.post("/webhook")
async def knowledge_webhook(
    event: dict,
    x_signature: str = Header(default=""),
    x_timestamp: str = Header(default=""),
) -> dict:
    """商品信息变更Webhook：HMAC签名验证 + 触发知识库热更新"""
    if not settings.api_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook未配置密钥")

    # 时间戳防重放
    try:
        ts = int(x_timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少有效时间戳")

    if abs(time.time() - ts) > WEBHOOK_TIMESTAMP_TOLERANCE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请求已过期")

    # HMAC 签名验证
    import json
    body = json.dumps(event, ensure_ascii=False, sort_keys=True)
    message = f"{x_timestamp}.{body}"
    expected = hmac.new(
        settings.api_secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="签名验证失败")

    return await updater.handle_webhook(event)
