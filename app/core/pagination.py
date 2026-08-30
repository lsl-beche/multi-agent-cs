"""分页助手：统一使用 SELECT COUNT 统计总数（避免全量拉取计数）"""
from typing import Any, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate(
    db: Session,
    query: Select,
    page: int = 1,
    page_size: int = 20,
    order_by: Any = None,
) -> tuple[Sequence[Any], int]:
    """执行分页查询，返回 (当前页数据, 总数)

    Args:
        db: 数据库会话
        query: 已应用过滤条件的 select 语句
        page: 页码（从1开始）
        page_size: 每页条数
        order_by: 排序表达式（如 Model.id.desc()）

    Returns:
        (rows, total)：当前页数据列表与符合条件的总记录数
    """
    # 总数统计：独立 COUNT 查询，不加载行数据
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # 数据查询：排序 + 分页
    if order_by is not None:
        query = query.order_by(order_by)
    rows = db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    return rows, total
