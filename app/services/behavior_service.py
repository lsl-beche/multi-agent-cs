"""推荐系统行为数据层：行为记录 + 加权交互矩阵（时间衰减） + ItemCF 相似度

权重：view=1, cart=3, collect=5, order=8, pay=10, review=2
时间衰减：exp(-age_days / 30)，近期行为权重更高
"""
import json
import logging
import math
import time
from datetime import datetime, timedelta
from typing import Dict, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.models.tables import Order, OrderItem, Product, UserBehavior

logger = logging.getLogger(__name__)

BEHAVIOR_WEIGHTS = {
    "view": 1,
    "cart": 3,
    "collect": 5,
    "order": 8,
    "pay": 10,
    "review": 2,
}
DECAY_HALF_DAYS = 30  # 行为权重半衰期（天）

_ITEM_SIM_KEY = "csagent:rec:item_sim"
_ITEM_SIM_TTL = 3600  # 1小时
_ITEM_SIM_TOP_N = 50  # 每个商品保留最相似的 N 个


def record(db: Session, user_id: int, product_id: int, behavior: str) -> bool:
    """记录一条用户行为（失败不影响主流程）"""
    if not user_id or not product_id or behavior not in BEHAVIOR_WEIGHTS:
        return False
    try:
        db.add(UserBehavior(user_id=user_id, product_id=product_id, behavior=behavior))
        db.commit()
        return True
    except Exception:
        logger.exception("record behavior failed: user=%s product=%s behavior=%s", user_id, product_id, behavior)
        return False


def weighted_matrix(db: Session, max_days: int = 365) -> dict[int, dict[int, float]]:
    """构建用户→商品 加权行为矩阵（时间衰减），并回填历史订单行为"""
    now = datetime.utcnow()
    cutoff = now - timedelta(days=max_days)
    matrix: dict[int, dict[int, float]] = {}

    def _add(uid: int, pid: int, weight: float, ts: datetime) -> None:
        age_days = max(0.0, (now - ts).total_seconds() / 86400)
        decay = math.exp(-age_days / DECAY_HALF_DAYS)
        val = weight * decay
        # 同用户同商品取最高权重行为，避免 view+order 叠加虚高
        matrix.setdefault(uid, {})
        matrix[uid][pid] = max(matrix[uid].get(pid, 0.0), val)

    # 1) 行为日志
    rows = db.execute(
        select(UserBehavior).where(UserBehavior.created_at >= cutoff)
    ).scalars().all()
    for r in rows:
        w = BEHAVIOR_WEIGHTS.get(r.behavior, 0)
        if w:
            _add(r.user_id, r.product_id, w, r.created_at)

    # 2) 回填历史订单（无行为日志时保证有数据）
    order_rows = db.execute(
        select(OrderItem.product_id, Order.user_id, Order.created_at)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.order_status.in_(["confirmed", "delivered", "completed"]))
    ).all()
    for pid, uid, ts in order_rows:
        _add(uid, pid, BEHAVIOR_WEIGHTS["order"], ts or now)

    return matrix


def user_cosine(a: dict[int, float], b: dict[int, float]) -> float:
    """用户行为向量的余弦相似度（加权）"""
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[p] * b[p] for p in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def build_item_similarity(db: Session, force: bool = False) -> dict[int, list[tuple[int, float]]]:
    """ItemCF：离线计算商品相似矩阵（余弦），缓存到 Redis"""
    if not force:
        try:
            raw = get_redis().get(_ITEM_SIM_KEY)
            if raw:
                data = json.loads(raw)
                return {int(k): [(int(a), float(s)) for a, s in v] for k, v in data.items()}
        except Exception:
            pass
    matrix = weighted_matrix(db)
    # product -> set(users)
    product_users: dict[int, set[int]] = {}
    for uid, prods in matrix.items():
        for pid in prods:
            product_users.setdefault(pid, set()).add(uid)
    sims: dict[int, list[tuple[int, float]]] = {}
    pids = list(product_users.keys())
    norm = {p: math.sqrt(len(product_users[p])) for p in pids}
    for i, p in enumerate(pids):
        scored = []
        for q in pids[i + 1:]:
            common = len(product_users[p] & product_users[q])
            if common == 0:
                continue
            s = common / (norm[p] * norm[q])
            if s > 0.01:
                scored.append((q, s))
                sims.setdefault(q, []).append((p, s))
        if scored:
            sims.setdefault(p, []).extend(scored)
    # 每商品保留 top-N
    result = {}
    for p, lst in sims.items():
        result[p] = sorted(lst, key=lambda x: -x[1])[:_ITEM_SIM_TOP_N]
    try:
        get_redis().setex(_ITEM_SIM_KEY, _ITEM_SIM_TTL, json.dumps(
            {str(k): [(a, s) for a, s in v] for k, v in result.items()}, ensure_ascii=False
        ))
    except Exception:
        pass
    return result
