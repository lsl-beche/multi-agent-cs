"""推荐系统 v1.1：ItemCF（缓存相似矩阵）→ 改进UserCF → 偏好 → 热销

数据：user_behavior 行为日志（加权+时间衰减）+ 历史订单回填
输出：带推荐理由（"买过A的人也买了B" / "根据您的偏好推荐" / "热门推荐"）
"""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Product, UserPreference
from app.services.async_bridge import async_adapter
from app.services.behavior_service import build_item_similarity, user_cosine, weighted_matrix


def _product_dict(p: Product, reason: str = "") -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.subtitle or (p.description or "")[:80],
        "category_id": p.category_id,
        "category_name": "",
        "images": [p.main_image] if p.main_image else [],
        "price": float(p.min_price or 0),
        "total_sales": p.total_sales,
        "reason": reason,
    }


def _itemcf_scores(user_items: dict[int, float], item_sim: dict[int, list[tuple[int, float]]], owned: set[int]):
    """ItemCF：用户行为商品 × 相似商品 加权求和，记录理由商品"""
    scores: Counter = Counter()
    reason_of: dict[int, int] = {}
    for pid, w in user_items.items():
        for other, sim in item_sim.get(pid, []):
            if other in owned:
                continue
            scores[other] += sim * w
            if other not in reason_of:
                reason_of[other] = pid
    return scores, reason_of


def _usercf_scores(user_id: int, matrix: dict[int, dict[int, float]], owned: set[int]):
    """改进 UserCF：余弦相似度加权，作为 ItemCF 的补充信号"""
    me = matrix.get(user_id, {})
    if not me:
        return Counter(), {}
    scores: Counter = Counter()
    reason_of: dict[int, int] = {}
    similar_users = []
    for uid, prods in matrix.items():
        if uid == user_id:
            continue
        sim = user_cosine(me, prods)
        if sim > 0.05:
            similar_users.append((uid, sim))
    similar_users.sort(key=lambda x: -x[1])
    for uid, sim in similar_users[:20]:
        for pid, w in matrix[uid].items():
            if pid in owned:
                continue
            scores[pid] += sim * w
            if pid not in reason_of:
                reason_of[pid] = uid
    return scores, reason_of


def recommend_for_user(db: Session, user_id: int | None, limit: int = 8) -> list[dict]:
    matrix = weighted_matrix(db)
    owned = set(matrix.get(user_id, {})) if user_id else set()
    user_items = matrix.get(user_id, {}) if user_id else {}
    item_sim = build_item_similarity(db)

    # 1) ItemCF 主推荐（可解释）
    scores, reason_of = _itemcf_scores(user_items, item_sim, owned)
    # 2) UserCF 补充（ItemCF 候选不足时）
    if len(scores) < limit * 2:
        extra_scores, extra_reason = _usercf_scores(user_id, matrix, owned)
        for pid, s in extra_scores.items():
            if pid not in scores:
                scores[pid] = s * 0.8  # UserCF 作为次级信号
                reason_of[pid] = extra_reason.get(pid, 0)

    all_online = db.execute(
        select(Product).where(Product.status == "online").order_by(Product.total_sales.desc())
    ).scalars().all()
    by_id = {p.id: p for p in all_online}

    result_ids: list[int] = []
    for pid, _score in scores.most_common():
        if pid in by_id and pid not in owned:
            result_ids.append(pid)
        if len(result_ids) >= limit:
            break

    # 3) 偏好类目补充
    pref_cats: list[str] = []
    pref_ids: set[int] = set()
    if user_id:
        try:
            row = db.execute(select(UserPreference).where(UserPreference.user_id == str(user_id))).scalar_one_or_none()
            if row:
                pref_cats = (row.profile or {}).get("favorite_categories", [])[:3]
        except Exception:
            pass
    if pref_cats:
        for p in all_online:
            if len(result_ids) >= limit:
                break
            if p.id in result_ids or p.id in owned:
                continue
            if p.category_id and any(c in (p.name or "") for c in pref_cats):
                result_ids.append(p.id)
                pref_ids.add(p.id)

    # 4) 热销兜底
    for p in all_online:
        if len(result_ids) >= limit:
            break
        if p.id not in result_ids and p.id not in owned:
            result_ids.append(p.id)

    # 组装推荐理由
    cf_ids = set(scores.keys())
    items = []
    for pid in result_ids[:limit]:
        p = by_id.get(pid)
        if not p:
            continue
        reason = ""
        if pid in reason_of:
            src = by_id.get(reason_of[pid])
            if src:
                reason = f"买过「{src.name}」的人也买了"
        elif pid in pref_ids:
            reason = "根据您的偏好推荐"
        elif pid not in cf_ids:
            reason = "热门推荐"
        items.append(_product_dict(p, reason))
    return items


recommend_for_user_async = async_adapter(recommend_for_user)
