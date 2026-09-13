"""用户偏好记忆（长期记忆之三）：LLM 从对话中提取结构化偏好，跨会话注入

提取流程：每 6 条会话消息（history%6==0），LLM 从最近 10 条对话中
抽取 JSON 偏好（口味/忌口/常关注品类/备注），与已有档案合并后存两份：
- Redis（csagent:pref:<uid>，TTL 30 天）：快速读取，注入每次对话上下文
- PostgreSQL（user_preferences 表）：持久化，Redis 丢失可恢复

隐私合规：
- user_memory_enabled=False 时完全关闭（不读不写）
- DELETE /api/user/memory 提供遗忘权（privacy_service 清除双份数据）

注入位置：chat.py _build_messages 会生成【用户偏好】SystemMessage，
让客服的回答贴合"用户喜欢浓茶/胃寒不宜绿茶"等个性化信息。
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.config.settings import settings
from app.core.db import SessionLocal
from app.core.llm import get_llm_for_task
from app.core.redis_client import get_redis
from app.dialogue.memory import SessionMemory
from app.models.tables import UserPreference

logger = logging.getLogger(__name__)

_PREFIX = "csagent:pref:"
_TTL = 60 * 60 * 24 * 30  # 30天

# 非茶叶品类词（防止把售后/订单话题误提取为"常关注品类"）
_CATEGORY_STOPWORDS = {
    "退款申请", "退款", "退货", "换货", "投诉", "转人工", "订单", "物流",
    "发票", "优惠券", "积分", "客服", "售后", "支付", "价格", "保存",
}

_EXTRACT_PROMPT = (
    "从以下客服对话中提取用户偏好，只输出JSON，不要解释：\n"
    '{{"taste_preference":"口味偏好，如浓/淡/甜/苦", '
    '"avoid":"忌口或不喜欢的茶/事项", '
    '"favorite_categories":["常关注的茶类或话题"], '
    '"note":"其他值得长期记住的信息，如身份、送礼需求、收藏偏好"}}'
    "\n没有的字段填空或空数组。\n\n对话：\n{text}"
)


def load_preferences(user_id: str) -> dict:
    """读取用户偏好：Redis 优先，PostgreSQL 兜底"""
    if not settings.user_memory_enabled:
        return {}
    if not user_id:
        return {}
    try:
        raw = get_redis().get(_PREFIX + user_id)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    # PostgreSQL 兜底
    try:
        db = SessionLocal()
        try:
            row = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            return dict(row.profile or {}) if row else {}
        finally:
            db.close()
    except Exception:
        return {}


def _store(user_id: str, profile: dict) -> None:
    """写入偏好：Redis + PostgreSQL"""
    if not settings.user_memory_enabled:
        return
    try:
        get_redis().setex(_PREFIX + user_id, _TTL, json.dumps(profile, ensure_ascii=False))
    except Exception:
        pass
    try:
        db = SessionLocal()
        try:
            row = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if row is None:
                row = UserPreference(user_id=user_id, profile=profile)
                db.add(row)
            else:
                row.profile = profile
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("store preference failed: user=%s", user_id)


def _merge(existing: dict, new: dict) -> dict:
    out = dict(existing or {})
    for k in ("taste_preference", "avoid", "note"):
        if new.get(k):
            out[k] = str(new[k])[:200]
    new_cats = [c for c in (new.get("favorite_categories") or []) if str(c).strip() not in _CATEGORY_STOPWORDS]
    cats = list(dict.fromkeys((out.get("favorite_categories") or []) + new_cats))
    out["favorite_categories"] = cats[:8]
    return out


def _extract_via_llm(text: str) -> dict:
    """调用 LLM 从对话中提取结构化偏好 JSON

    prompt 给出字段说明（taste_preference/avoid/favorite_categories/note），
    要求只输出 JSON；解析失败返回空字典（不影响主流程）。
    """
    try:
        llm = get_llm_for_task("preferences", max_tokens=128, streaming=False)
        resp = llm.invoke([
            SystemMessage(content="你是用户画像提取助手，只输出JSON。"),
            HumanMessage(content=_EXTRACT_PROMPT.format(text=text[:3000])),
        ])
        content = (resp.content or "").strip()
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start:end + 1])
    except Exception:
        logger.exception("preference extract failed")
    return {}


def update_preferences(user_id: str, session_id: str) -> dict:
    """从最近对话提取并合并用户偏好（后台调用，失败不阻断）"""
    if not user_id or not session_id:
        return {}
    try:
        history = SessionMemory().load(session_id)
        if len(history) < 4:  # 至少两轮对话再提取
            return load_preferences(user_id)
        text = "\n".join(f"{'用户' if h['role'] == 'user' else '客服'}：{h['content'][:200]}" for h in history[-10:])
        new = _extract_via_llm(text)
        if not new:
            return load_preferences(user_id)
        merged = _merge(load_preferences(user_id), new)
        _store(user_id, merged)
        return merged
    except Exception:
        logger.exception("update_preferences failed")
        return load_preferences(user_id)


def build_preference_prompt(user_id: str) -> str | None:
    """生成注入 LLM 上下文的用户偏好描述"""
    p = load_preferences(user_id)
    parts = []
    if p.get("taste_preference"):
        parts.append(f"口味偏好：{p['taste_preference']}")
    if p.get("avoid"):
        parts.append(f"忌口/不喜欢：{p['avoid']}")
    if p.get("favorite_categories"):
        parts.append("常关注：" + "、".join(p["favorite_categories"]))
    if p.get("note"):
        parts.append(f"备注：{p['note']}")
    return "；".join(parts) if parts else None
