"""商品管理路由"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, run_sync
from app.api.middleware.auth import require_permission
from app.models.schemas import CategoryCreate, ProductCreate, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter()


# ── 商品 ──

@router.get("", summary="商品列表")
async def list_products(
    user: dict = Depends(require_permission("products", "read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    data, total = await run_sync(db, ProductService.list_products, page, page_size, keyword, category_id, status, sort_by, sort_dir)
    return {"code": 0, "data": data, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="创建商品")
async def create_product(body: ProductCreate, user: dict = Depends(require_permission("products", "create")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, ProductService.create_product, body.model_dump())
        return {"code": 0, "data": result, "message": "创建成功"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{product_id}", summary="商品详情")
async def get_product(product_id: int, user: dict = Depends(require_permission("products", "read")), db: AsyncSession = Depends(get_db)):
    try:
        return {"code": 0, "data": await run_sync(db, ProductService.get_product, product_id)}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.put("/{product_id}", summary="更新商品")
async def update_product(product_id: int, body: ProductUpdate, user: dict = Depends(require_permission("products", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, ProductService.update_product, product_id, body.model_dump(exclude_none=True))
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/{product_id}", summary="下架商品")
async def delete_product(product_id: int, user: dict = Depends(require_permission("products", "delete")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, ProductService.delete_product, product_id)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.put("/{product_id}/online", summary="上架商品")
async def online_product(product_id: int, user: dict = Depends(require_permission("products", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, ProductService.toggle_online, product_id, True)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.put("/{product_id}/offline", summary="下架商品")
async def offline_product(product_id: int, user: dict = Depends(require_permission("products", "update")), db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, ProductService.toggle_online, product_id, False)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# ── 类目 ──

@router.get("/categories/all", summary="类目树")
async def list_categories(user: dict = Depends(require_permission("products", "read")), db: AsyncSession = Depends(get_db)):
    data = await run_sync(db, ProductService.list_categories)
    return {"code": 0, "data": data}


@router.post("/categories", summary="创建类目")
async def create_category(body: CategoryCreate, user: dict = Depends(require_permission("products", "create")), db: AsyncSession = Depends(get_db)):
    result = await run_sync(db, ProductService.create_category, body.name, body.parent_id, body.level, body.sort_order)
    return {"code": 0, "data": result}


@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("products", "update")),
    db: AsyncSession = Depends(get_db)
):
    """上传商品图片，返回URL"""
    # Validate
    ext = os.path.splitext(file.filename or "image.png")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(400, "仅支持 jpg/png/webp 格式")

    # Save to static/products/
    static_dir = Path(__file__).resolve().parent.parent.parent.parent / "static" / "products"
    static_dir.mkdir(parents=True, exist_ok=True)

    filename = f"prod_{uuid.uuid4().hex[:8]}{ext}"
    filepath = static_dir / filename

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "图片大小不能超过10MB")

    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/static/products/{filename}"
    return {"code": 0, "data": {"url": url, "filename": filename}}
