"""商品服务：CRUD + 全文搜索 + 级联创建（含SKU+库存）"""
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.tables import Category, Inventory, Product, ProductImage, Sku


class ProductService:

    @staticmethod
    def list_products(db: Session, page: int = 1, page_size: int = 20,
                      keyword: str | None = None, category_id: int | None = None,
                      status: str | None = None, sort_by: str = "id", sort_dir: str = "desc") -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Product)

        if keyword:
            query = query.where(
                Product.name.ilike(f"%{keyword}%") |
                Product.spu_code.ilike(f"%{keyword}%")
            )
        if category_id:
            cat_ids = ProductService._get_subcategory_ids(db, category_id)
            query = query.where(Product.category_id.in_(cat_ids))
        if status:
            query = query.where(Product.status == status)

        order_col = getattr(Product, sort_by, Product.id)
        order_by = order_col.asc() if sort_dir == "asc" else order_col.desc()
        rows, total = paginate(db, query, page, page_size, order_by=order_by)

        result = []
        for p in rows:
            cat = db.execute(select(Category.name).where(Category.id == p.category_id)).scalar()
            result.append({
                "id": p.id, "spu_code": p.spu_code, "name": p.name,
                "subtitle": p.subtitle, "category_name": cat,
                "brand": p.brand, "main_image": p.main_image,
                "status": p.status, "min_price": float(p.min_price), "max_price": float(p.max_price),
                "total_sales": p.total_sales,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })
        return result, total

    @staticmethod
    def _get_subcategory_ids(db: Session, category_id: int) -> list[int]:
        """获取类目及其所有子类目ID"""
        ids = [category_id]
        children = db.execute(
            select(Category.id).where(Category.parent_id == category_id)
        ).scalars().all()
        for cid in children:
            ids.extend(ProductService._get_subcategory_ids(db, cid))
        return ids

    @staticmethod
    def create_product(db: Session, data: dict) -> dict:
        skus_data = data.pop("skus", [])
        images_data = data.pop("images", [])

        product = Product(**data)
        db.add(product)
        db.flush()

        # 图片
        for img in images_data:
            db.add(ProductImage(product_id=product.id, **img))

        # SKU + 库存
        for sdata in skus_data:
            stock = sdata.pop("stock", 0)
            sku = Sku(
                sku_code=sdata["sku_code"],
                product_id=product.id,
                spec_info=sdata.get("spec_info", {}),
                price=sdata["price"],
                original_price=sdata.get("original_price"),
                barcode=sdata.get("barcode"),
            )
            db.add(sku)
            db.flush()
            db.add(Inventory(sku_id=sku.id, quantity=stock))

        # 更新min_price/max_price
        prices = [s["price"] for s in skus_data]
        product.min_price = min(prices) if prices else 0
        product.max_price = max(prices) if prices else 0

        db.commit()
        return {"id": product.id, "spu_code": product.spu_code, "name": product.name}

    @staticmethod
    def get_product(db: Session, product_id: int) -> dict:
        p = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
        if not p:
            raise ValueError("商品不存在")

        images = db.execute(
            select(ProductImage).where(ProductImage.product_id == p.id).order_by(ProductImage.sort_order)
        ).scalars().all()

        skus = db.execute(select(Sku).where(Sku.product_id == p.id)).scalars().all()
        sku_list = []
        for s in skus:
            inv = db.execute(select(Inventory).where(Inventory.sku_id == s.id)).scalar_one_or_none()
            sku_list.append({
                "id": s.id, "sku_code": s.sku_code,
                "spec_info": s.spec_info, "price": float(s.price),
                "original_price": float(s.original_price) if s.original_price else None,
                "barcode": s.barcode, "status": s.status,
                "stock": inv.quantity if inv else 0,
            })

        cat = db.execute(select(Category.name).where(Category.id == p.category_id)).scalar()

        return {
            "id": p.id, "spu_code": p.spu_code, "name": p.name,
            "subtitle": p.subtitle, "category_id": p.category_id, "category_name": cat,
            "brand": p.brand, "main_image": p.main_image, "description": p.description,
            "status": p.status, "min_price": float(p.min_price), "max_price": float(p.max_price),
            "total_sales": p.total_sales,
            "images": [{"id": img.id, "url": img.url, "sort_order": img.sort_order, "is_main": img.is_main} for img in images],
            "skus": sku_list,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }

    @staticmethod
    def update_product(db: Session, product_id: int, data: dict) -> dict:
        p = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
        if not p:
            raise ValueError("商品不存在")

        # Handle images if provided
        images_data = data.pop("images", None)

        for key, val in data.items():
            if val is not None:
                setattr(p, key, val)

        if images_data is not None:
            # Delete existing images
            db.query(ProductImage).filter(ProductImage.product_id == product_id).delete()
            # Add new images
            for img_data in images_data:
                image = ProductImage(
                    product_id=product_id,
                    url=img_data["url"],
                    sort_order=img_data.get("sort_order", 0),
                    is_main=img_data.get("is_main", False),
                )
                db.add(image)

        db.commit()
        return {"id": p.id, "name": p.name}

    @staticmethod
    def delete_product(db: Session, product_id: int) -> dict:
        p = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
        if not p:
            raise ValueError("商品不存在")
        p.status = "offline"
        db.commit()
        return {"id": p.id, "status": p.status}

    @staticmethod
    def toggle_online(db: Session, product_id: int, online: bool) -> dict:
        p = db.execute(select(Product).where(Product.id == product_id)).scalar_one_or_none()
        if not p:
            raise ValueError("商品不存在")
        p.status = "online" if online else "offline"
        db.commit()
        return {"id": p.id, "status": p.status}

    # ── 类目 ──

    @staticmethod
    def list_categories(db: Session) -> list[dict]:
        rows = db.execute(
            select(Category).order_by(Category.level, Category.sort_order)
        ).scalars().all()
        return [{
            "id": c.id, "name": c.name, "parent_id": c.parent_id,
            "level": c.level, "sort_order": c.sort_order,
        } for c in rows]

    @staticmethod
    def create_category(db: Session, name: str, parent_id: int | None = None, level: int = 1, sort_order: int = 0) -> dict:
        cat = Category(name=name, parent_id=parent_id, level=level, sort_order=sort_order)
        db.add(cat)
        db.commit()
        return {"id": cat.id, "name": cat.name}

    @staticmethod
    def search_products(db: Session, keyword: str, limit: int = 5) -> list[dict]:
        """客服工具：按关键词搜索在售商品，返回价格与库存摘要"""
        if not keyword:
            return []
        rows = db.execute(
            select(Product)
            .where(Product.status == "online", Product.name.ilike(f"%{keyword}%"))
            .order_by(Product.total_sales.desc())
            .limit(limit)
        ).scalars().all()
        result = []
        for p in rows:
            skus = db.execute(select(Sku).where(Sku.product_id == p.id)).scalars().all()
            total_stock = 0
            sku_list = []
            for s in skus:
                inv = db.execute(select(Inventory).where(Inventory.sku_id == s.id)).scalar_one_or_none()
                qty = inv.quantity if inv else 0
                total_stock += qty
                sku_list.append({"sku_code": s.sku_code, "price": float(s.price), "stock": qty})
            min_price = min((float(s.price) for s in skus), default=float(p.min_price or 0))
            result.append({
                "id": p.id,
                "name": p.name,
                "price": min_price,
                "stock": total_stock,
                "skus": sku_list,
            })
        return result

    @staticmethod
    def check_stock(db: Session, sku_code: str) -> dict:
        """客服工具：按SKU编码预检库存"""
        s = db.execute(select(Sku).where(Sku.sku_code == sku_code)).scalar_one_or_none()
        if not s:
            return {"error": "not_found", "message": f"未找到SKU {sku_code}"}
        inv = db.execute(select(Inventory).where(Inventory.sku_id == s.id)).scalar_one_or_none()
        qty = inv.quantity if inv else 0
        return {
            "sku_code": sku_code,
            "product": s.product.name if s.product else "",
            "stock": qty,
            "available": qty > 0,
        }
