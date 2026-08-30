"""补足商品库到指定数量（默认 500）：幂等、可中断续跑

用法：
    python scripts/seed_to_500.py            # 补足到 500
    python scripts/seed_to_500.py --target 800
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_100_products import (
    BRANDS,
    DESCRIPTIONS,
    SPEC_COMBOS,
    TEA_NAMES,
    calculate_price,
    generate_sku_code,
)
from sqlalchemy import func, select, text

from app.core.db import SessionLocal
from app.models.tables import Category, Inventory, Product, ProductImage, Sku

# 真实存在的商品图（优先使用，避免404占位）
REAL_IMAGES = [
    "/static/products/puer_main.jpg",
    "/static/products/longjing_main.jpg",
    "/static/products/jinjunmei_main.jpg",
    "/static/products/dahongpao_main.jpg",
    "/static/products/biluochun_main.jpg",
    "/static/products/baihao_main.jpg",
    "/static/products/prod_ceeed32f.jpg",
]

# 品类名 → 数据库类目名（数据库为"普洱茶"，生成器为"普洱"）
CATEGORY_MAP = {
    "绿茶": "绿茶",
    "红茶": "红茶",
    "乌龙茶": "乌龙茶",
    "普洱": "普洱茶",
    "白茶": "白茶",
    "花茶": "花茶",
    "养生茶": "养生茶",
}


def ensure_categories(db) -> dict[str, int]:
    """确保顶级/二级类目齐全，返回 {名称: id}"""
    # 同步主键序列，避免新类目 ID 与已有行冲突
    db.execute(text("SELECT setval(pg_get_serial_sequence('categories','id'), (SELECT COALESCE(MAX(id),1) FROM categories))"))
    tea = db.execute(select(Category).where(Category.name == "茶叶", Category.parent_id.is_(None))).scalar_one_or_none()
    if not tea:
        tea = Category(name="茶叶", parent_id=None, level=1, sort_order=1)
        db.add(tea)
        db.flush()
    by_name = {c.name: c.id for c in db.query(Category).all()}
    for name in CATEGORY_MAP.values():
        if name not in by_name:
            cat = Category(name=name, parent_id=tea.id, level=2)
            db.add(cat)
            db.flush()
            by_name[name] = cat.id
    return by_name


def generate(db, target: int = 500) -> int:
    total = db.execute(select(func.count(Product.id))).scalar() or 0
    need = max(0, target - total)
    if need == 0:
        print(f"商品库已是 {total} 件，无需补充")
        return 0
    print(f"当前 {total} 件，需补充 {need} 件...")

    by_name = ensure_categories(db)
    existing_names = {row[0] for row in db.query(Product.name).all()}
    existing_codes = {row[0] for row in db.query(Product.spu_code).all()}
    max_num = 20240000
    for code in existing_codes:
        try:
            max_num = max(max_num, int(code[3:]))
        except ValueError:
            pass

    created = 0
    attempts = 0
    status_pool = ["online"] * 4 + ["offline"]  # 80% 上架
    while created < need and attempts < need * 30:
        attempts += 1
        cat_key = random.choice(list(CATEGORY_MAP.keys()))
        tea_name = random.choice(TEA_NAMES[cat_key])
        brand = random.choice(BRANDS)
        full_name = f"{brand} {tea_name}"
        if full_name in existing_names:
            continue
        existing_names.add(full_name)

        spu_code = f"SPU{max_num + created + 1:08d}"
        status = random.choice(status_pool)
        base_price = round(random.uniform(80, 800), 2)
        num_skus = random.choice([1, 1, 2, 2, 3])
        spec_combos = random.sample(SPEC_COMBOS, min(num_skus, len(SPEC_COMBOS)))

        product = Product(
            spu_code=spu_code,
            name=full_name,
            subtitle=f"{brand}出品 · {tea_name} · {cat_key}",
            category_id=by_name.get(CATEGORY_MAP[cat_key]),
            brand=brand,
            main_image=random.choice(REAL_IMAGES),
            description=DESCRIPTIONS.get(cat_key, DESCRIPTIONS["绿茶"]),
            status=status,
            min_price=0,
            max_price=0,
            total_sales=random.randint(0, 5000) if status == "online" else 0,
        )
        db.add(product)
        db.flush()

        prices = []
        for si, combo in enumerate(spec_combos):
            sku_code = generate_sku_code(spu_code, si)
            price = calculate_price(base_price, combo)
            original_price = round(price * random.uniform(1.2, 1.8), 2)
            prices.append(price)
            sku = Sku(
                sku_code=sku_code,
                product_id=product.id,
                spec_info=combo,
                price=price,
                original_price=original_price,
                barcode=f"6{random.randint(900000000000, 999999999999)}",
                status="online",
            )
            db.add(sku)
            db.flush()
            db.add(Inventory(
                sku_id=sku.id,
                warehouse_id=1,
                quantity=random.randint(50, 2000),
                locked_quantity=0,
                safety_stock=random.randint(10, 50),
            ))

        product.min_price = min(prices)
        product.max_price = max(prices)
        for img_idx in range(1, random.randint(2, 4)):
            db.add(ProductImage(
                product_id=product.id,
                url=random.choice(REAL_IMAGES),
                sort_order=img_idx,
                is_main=(img_idx == 1),
            ))
        created += 1
        if created % 50 == 0:
            db.commit()
            print(f"  已生成 {created}/{need}")

    db.commit()
    final = db.execute(select(func.count(Product.id))).scalar() or 0
    print(f"完成：新增 {created} 件，商品库现有 {final} 件")
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=500)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        generate(db, args.target)
    finally:
        db.close()
