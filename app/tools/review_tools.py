"""评价工具：按商品关键词查询已通过的用户评价

供知识 Agent 的"评价/口碑"类问题使用：
自动清洗提问词后按商品名搜索，返回已通过审核的评价摘要。
"""
import json

from langchain_core.tools import tool

from app.core.db import SessionLocal
from app.services.review_service import ReviewService
from app.tools.registry import register


@tool
def search_reviews(keyword: str) -> str:
    """用户评价查询：按商品名称关键词搜索已通过的评价内容。参数 keyword 为商品关键词。"""
    db = SessionLocal()
    try:
        return json.dumps(ReviewService.search_reviews(db, keyword), ensure_ascii=False)
    finally:
        db.close()


register(search_reviews)
