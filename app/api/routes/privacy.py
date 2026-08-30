"""隐私合规接口：记忆开关状态 / 隐私政策说明 / 遗忘权指引"""
from fastapi import APIRouter

from app.config.settings import settings

router = APIRouter()


@router.get("/privacy", summary="隐私合规说明")
async def privacy() -> dict:
    """返回当前隐私配置：是否启用偏好/向量记忆，及遗忘权入口"""
    return {
        "code": 0,
        "data": {
            "memory_enabled": settings.user_memory_enabled,
            "memory_ttl_days": settings.memory_ttl_days,
            "erase_endpoint": "DELETE /api/user/memory（需登录）",
            "policy": "仅存储客服对话所必需的信息（偏好/会话/向量记忆），"
                      "不采集身份证、支付密码等敏感信息；可随时一键清除。",
        },
    }
