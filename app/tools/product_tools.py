"""商品相关工具：商品搜索、库存预检

对应 ProductService 的 search_products / check_stock，
供以下场景使用：
- 知识 Agent 的"库存/现货"类问题（规则层预取，注入上下文）
- 云端 tool-calling 模式的商品检索
"""
import json

from langchain_core.tools import tool

from app.core.db import SessionLocal
from app.services import product_service
from app.tools.registry import register


@tool
def search_product(keyword: str) -> str:
    """商品搜索：按关键词查询商品信息、价格与库存。参数 keyword 为搜索关键词。"""
    db = SessionLocal()
    try:
        return json.dumps(product_service.ProductService.search_products(db, keyword), ensure_ascii=False)
    finally:
        db.close()


@tool
def check_stock(sku_id: str) -> str:
    """库存预检：查询指定SKU的库存状态。参数 sku_id 为商品SKU编码。"""
    db = SessionLocal()
    try:
        return json.dumps(product_service.ProductService.check_stock(db, sku_id), ensure_ascii=False)
    finally:
        db.close()


register(search_product)
register(check_stock)
