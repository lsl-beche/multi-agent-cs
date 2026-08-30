"""推荐系统离线评测报告：行为矩阵 / 覆盖率 / 多样性 / 延迟"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.tables import Product, UserBehavior
from app.services.behavior_service import build_item_similarity, weighted_matrix
from app.services.recommend_service import recommend_for_user


def main() -> None:
    db = SessionLocal()
    t0 = time.time()
    matrix = weighted_matrix(db)
    matrix_sec = round(time.time() - t0, 3)

    # 行为统计
    total_rows = db.execute(select(func.count(UserBehavior.id))).scalar() or 0
    behavior_dist = dict(db.execute(
        select(UserBehavior.behavior, func.count(UserBehavior.id)).group_by(UserBehavior.behavior)
    ).all())

    # ItemCF 相似矩阵
    t0 = time.time()
    item_sim = build_item_similarity(db, force=True)
    sim_sec = round(time.time() - t0, 3)
    sim_items = len(item_sim)
    sim_pairs = sum(len(v) for v in item_sim.values())

    # 推荐质量：样本用户
    sample_users = sorted(matrix, key=lambda u: -len(matrix[u]))[:5]
    total_cats: set = set()
    per_user_hits = []
    latencies = []
    for uid in sample_users:
        t0 = time.time()
        items = recommend_for_user(db, uid, 8)
        latencies.append(round((time.time() - t0) * 1000, 1))
        cats = {i.get("category_id") for i in items if i.get("category_id")}
        total_cats |= cats
        per_user_hits.append({
            "user": uid,
            "behaviors": len(matrix.get(uid, {})),
            "items": len(items),
            "reasons": sum(1 for i in items if i.get("reason")),
            "categories": len(cats),
        })

    online_count = db.execute(select(func.count(Product.id)).where(Product.status == "online")).scalar() or 1
    report = {
        "behavior_rows": total_rows,
        "behavior_distribution": behavior_dist,
        "matrix_users": len(matrix),
        "matrix_entries": sum(len(v) for v in matrix.values()),
        "matrix_build_seconds": matrix_sec,
        "item_sim": {"items": sim_items, "pairs": sim_pairs, "build_seconds": sim_sec},
        "sample_users": per_user_hits,
        "coverage": round(len(total_cats) / max(1, online_count), 3),
        "avg_latency_ms": round(sum(latencies) / max(1, len(latencies)), 1),
    }
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
