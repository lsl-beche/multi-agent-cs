"""C 端商品路由：商品列表/详情/类目/推荐"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.product_service import ProductService

router = APIRouter()


@router.get("", summary="商品列表")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    category_id: int | None = None,
    sort: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """C端商品列表，只返回已上架商品"""
    sort_by, sort_dir = "id", "desc"
    if sort == "price_asc":
        sort_by, sort_dir = "min_price", "asc"
    elif sort == "price_desc":
        sort_by, sort_dir = "min_price", "desc"

    items, total = await ProductService.list_products_async(
        db,
        page=page, page_size=page_size,
        keyword=keyword, category_id=category_id,
        status="online", sort_by=sort_by, sort_dir=sort_dir,
    )

    # 为每个商品添加 price 和 images 字段供前端使用
    result = []
    for p in items:
        images = [img.get("url", "") for img in (p.get("images") or [])]
        if not images and p.get("main_image"):
            images = [p["main_image"]]  # list未返回多图时用主图兜底
        result.append({
            "id": p["id"],
            "name": p["name"],
            "description": p.get("subtitle") or p.get("description", ""),
            "category_id": p.get("category_id"),
            "category_name": p.get("category_name", ""),
            "images": images,
            "price": float(p.get("min_price", 0)),
            "status": p.get("status", ""),
            "created_at": str(p.get("created_at", "")),
            "total_sales": p.get("total_sales", 0),
        })

    return {"code": 0, "data": {"items": result, "total": total}}


@router.get("/categories/all", summary="全部分类")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """返回扁平分类列表（前端自行构建树）"""
    data = await ProductService.list_categories_async(db)
    return {"code": 0, "data": data}


@router.get("/recommend", summary="为你推荐（协同过滤+偏好+热销）")
async def recommend(
    request: Request,
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    user_id = None
    try:
        from app.api.deps import current_user
        payload = await current_user(request)
        user_id = int(payload["sub"])
    except Exception:
        user_id = None
    from app.services.recommend_service import recommend_for_user_async
    items = await recommend_for_user_async(db, user_id, limit)
    return {"code": 0, "data": {"items": items, "total": len(items)}}


@router.get("/{product_id}", summary="商品详情")
async def product_detail(product_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        product = await ProductService.get_product_async(db, product_id)
    except ValueError:
        return {"code": 1, "message": "商品不存在"}

    if not product:
        return {"code": 1, "message": "商品不存在"}

    # 行为日志：浏览（登录用户）
    try:
        from app.api.deps import current_user
        payload = await current_user(request)
        from app.services.behavior_service import record_async
        await record_async(db, int(payload["sub"]), product["id"], "view")
    except Exception:
        pass  # 未登录或记录失败不影响详情返回

    images = [img.get("url", "") for img in (product.get("images") or [])]
    skus = []
    for s in product.get("skus") or []:
        skus.append({
            "id": s["id"],
            "product_id": product["id"],
            "name": s.get("sku_code", ""),
            "price": float(s.get("price", 0)),
            "stock": s.get("stock", 0),
            "attrs": s.get("spec_info") or {},
        })

    return {
        "code": 0,
        "data": {
            "id": product["id"],
            "name": product["name"],
            "description": product.get("subtitle") or product.get("description", ""),
            "category_id": product.get("category_id"),
            "category_name": product.get("category_name", ""),
            "images": images,
            "price": float(product.get("min_price", 0)),
            "skus": skus,
        },
    }
