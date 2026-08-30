"""种子数据填充脚本：初始化系统运行所需的基础数据

用法：
    python scripts/seed_data.py           # 填充全部种子数据
    python scripts/seed_data.py --reset   # 清空后重新填充（⚠ 数据丢失）

填充内容：
    1. 角色+权限（super_admin / admin / operator / viewer）
    2. 管理员账户（admin/admin123）
    3. 商品类目（三级茶品类目树）
    4. 示例商品（6款茶叶产品含SKU+库存）
    5. 优惠券模板
    6. 示例用户
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime

import bcrypt
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.models.tables import (
    Category,
    # 营销
    Coupon,
    Inventory,
    Permission,
    Product,
    ProductImage,
    # 评价
    Review,
    # 权限
    Role,
    RolePermission,
    Sku,
    # 用户
    User,
    UserRole,
)

# ── 角色定义 ────────────────────────────────────────
ROLES = [
    ("super_admin", "超级管理员"),
    ("admin", "管理员"),
    ("operator", "运营人员"),
    ("viewer", "只读用户"),
]

# ── 权限定义 ────────────────────────────────────────
PERMISSIONS = {
    "products": ["create", "read", "update", "delete", "export"],
    "orders": ["create", "read", "update", "delete", "export"],
    "users": ["create", "read", "update", "delete", "export"],
    "inventory": ["read", "update", "export"],
    "payments": ["read", "export"],
    "shipments": ["create", "read", "update"],
    "coupons": ["create", "read", "update", "delete"],
    "promotions": ["create", "read", "update", "delete"],
    "reviews": ["read", "update"],
    "reports": ["read", "export"],
    "tickets": ["create", "read", "update"],
    "system": ["read", "update"],
}

# ── 角色⇄权限映射 ────────────────────────────────────
ROLE_PERMISSIONS = {
    "super_admin": {f"{r}:{a}" for r in PERMISSIONS for a in PERMISSIONS[r]},
    "admin": {
        "products:create", "products:read", "products:update", "products:export",
        "orders:create", "orders:read", "orders:update", "orders:export",
        "users:read", "users:update",
        "inventory:read", "inventory:update", "inventory:export",
        "payments:read", "payments:export",
        "shipments:create", "shipments:read", "shipments:update",
        "coupons:create", "coupons:read", "coupons:update",
        "promotions:create", "promotions:read", "promotions:update",
        "reviews:read", "reviews:update",
        "reports:read", "reports:export",
        "tickets:create", "tickets:read", "tickets:update",
    },
    "operator": {
        "products:read", "products:update",
        "orders:read", "orders:update",
        "users:read",
        "inventory:read", "inventory:update",
        "payments:read",
        "shipments:read", "shipments:update",
        "coupons:read",
        "promotions:read",
        "reviews:read",
        "reports:read",
        "tickets:read", "tickets:update",
    },
    "viewer": {
        "products:read", "orders:read", "users:read",
        "inventory:read", "payments:read", "shipments:read",
        "coupons:read", "promotions:read", "reviews:read",
        "reports:read", "tickets:read",
    },
}

# ── 类目树 ──────────────────────────────────────────
CATEGORIES = [
    # (id, name, parent_id, level, sort)
    (1, "茶叶", None, 1, 1),
    (2, "茶具", None, 1, 2),
    (3, "茶食品", None, 1, 3),
    # 茶叶子类
    (4, "绿茶", 1, 2, 1),
    (5, "红茶", 1, 2, 2),
    (6, "乌龙茶", 1, 2, 3),
    (7, "普洱茶", 1, 2, 4),
    (8, "白茶", 1, 2, 5),
    (9, "花茶", 1, 2, 6),
    # 茶具子类
    (10, "茶壶", 2, 2, 1),
    (11, "茶杯", 2, 2, 2),
    (12, "茶盘", 2, 2, 3),
    # 三级
    (13, "西湖龙井", 4, 3, 1),
    (14, "碧螺春", 4, 3, 2),
    (15, "金骏眉", 5, 3, 1),
    (16, "正山小种", 5, 3, 2),
    (17, "铁观音", 6, 3, 1),
    (18, "大红袍", 6, 3, 2),
    (19, "生普洱", 7, 3, 1),
    (20, "熟普洱", 7, 3, 2),
    (21, "白毫银针", 8, 3, 1),
    (22, "茉莉花茶", 9, 3, 1),
]

# ── 示例商品 ─────────────────────────────────────────
DEMO_PRODUCTS = [
    {
        "spu_code": "SPU20240001",
        "name": "明前特级西湖龙井 250g",
        "subtitle": "核心产区 正宗狮峰明前茶",
        "category_id": 13,
        "brand": "御茶园",
        "main_image": "/static/products/longjing_main.jpg",
        "description": "<p>产自杭州西湖核心产区，明前手工采摘一芽一叶，色泽翠绿，香郁味醇。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/longjing_1.jpg", "sort_order": 0, "is_main": True},
            {"url": "/static/products/longjing_2.jpg", "sort_order": 1, "is_main": False},
        ],
        "skus": [
            {"sku_code": "SKU20240001001", "spec": {"规格": "250g", "包装": "简装"},
             "price": 168.00, "original_price": 198.00, "barcode": "6901234001001", "stock": 500},
            {"sku_code": "SKU20240001002", "spec": {"规格": "500g", "包装": "礼盒装"},
             "price": 328.00, "original_price": 398.00, "barcode": "6901234001002", "stock": 200},
            {"sku_code": "SKU20240001003", "spec": {"规格": "100g", "包装": "试饮装"},
             "price": 78.00, "original_price": 88.00, "barcode": "6901234001003", "stock": 800},
        ],
    },
    {
        "spu_code": "SPU20240002",
        "name": "武夷山正岩大红袍 200g",
        "subtitle": "岩骨花香 乌龙茶之极品",
        "category_id": 18,
        "brand": "武夷岩韵",
        "main_image": "/static/products/dahongpao_main.jpg",
        "description": "<p>产自武夷山正岩产区，传统炭焙工艺，岩韵明显，回甘持久。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/dahongpao_1.jpg", "sort_order": 0, "is_main": True},
        ],
        "skus": [
            {"sku_code": "SKU20240002001", "spec": {"规格": "200g", "包装": "牛皮纸袋"},
             "price": 288.00, "original_price": 358.00, "barcode": "6901234002001", "stock": 150},
            {"sku_code": "SKU20240002002", "spec": {"规格": "400g", "包装": "礼盒装"},
             "price": 558.00, "original_price": 688.00, "barcode": "6901234002002", "stock": 60},
        ],
    },
    {
        "spu_code": "SPU20240003",
        "name": "云南古树普洱茶饼 357g",
        "subtitle": "百年古树 生普经典",
        "category_id": 19,
        "brand": "勐海古韵",
        "main_image": "/static/products/puer_main.jpg",
        "description": "<p>精选云南勐海百年以上古树春茶，石磨压制饼茶，越陈越香。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/puer_1.jpg", "sort_order": 0, "is_main": True},
        ],
        "skus": [
            {"sku_code": "SKU20240003001", "spec": {"年份": "2024年春", "规格": "357g饼"},
             "price": 238.00, "original_price": 298.00, "barcode": "6901234003001", "stock": 300},
            {"sku_code": "SKU20240003002", "spec": {"年份": "2020年春", "规格": "357g饼"},
             "price": 468.00, "original_price": 568.00, "barcode": "6901234003002", "stock": 80},
        ],
    },
    {
        "spu_code": "SPU20240004",
        "name": "金骏眉红茶特级 150g",
        "subtitle": "武夷山桐木关 芽尖金毫",
        "category_id": 15,
        "brand": "武夷岩韵",
        "main_image": "/static/products/jinjunmei_main.jpg",
        "description": "<p>正宗桐木关金骏眉，单芽采摘，金黄黑相间，花果蜜香馥郁。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/jinjunmei_1.jpg", "sort_order": 0, "is_main": True},
        ],
        "skus": [
            {"sku_code": "SKU20240004001", "spec": {"规格": "150g", "包装": "铁罐装"},
             "price": 388.00, "original_price": 488.00, "barcode": "6901234004001", "stock": 120},
        ],
    },
    {
        "spu_code": "SPU20240005",
        "name": "福鼎白毫银针 100g",
        "subtitle": "头采白毫 清甜醇爽",
        "category_id": 21,
        "brand": "福鼎白茶坊",
        "main_image": "/static/products/baihao_main.jpg",
        "description": "<p>福鼎核心产区头采芽头，满披白毫如银似雪，口感清甜醇爽。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/baihao_1.jpg", "sort_order": 0, "is_main": True},
        ],
        "skus": [
            {"sku_code": "SKU20240005001", "spec": {"年份": "2024年春", "规格": "100g"},
             "price": 268.00, "original_price": 338.00, "barcode": "6901234005001", "stock": 90},
        ],
    },
    {
        "spu_code": "SPU20240006",
        "name": "苏州碧螺春特级 200g",
        "subtitle": "洞庭山原产地 花果香浓郁",
        "category_id": 14,
        "brand": "御茶园",
        "main_image": "/static/products/biluochun_main.jpg",
        "description": "<p>苏州洞庭山原产，传统工艺炒制，条索纤细卷曲，花果香馥郁持久。</p>",
        "status": "online",
        "images": [
            {"url": "/static/products/biluochun_1.jpg", "sort_order": 0, "is_main": True},
        ],
        "skus": [
            {"sku_code": "SKU20240006001", "spec": {"规格": "200g", "包装": "铁罐装"},
             "price": 198.00, "original_price": 258.00, "barcode": "6901234006001", "stock": 180},
            {"sku_code": "SKU20240006002", "spec": {"规格": "400g", "包装": "礼盒装"},
             "price": 388.00, "original_price": 488.00, "barcode": "6901234006002", "stock": 70},
        ],
    },
]

# ── 优惠券模板 ──────────────────────────────────────
DEMO_COUPONS = [
    {"name": "新用户满99减15", "coupon_type": "fixed", "threshold": 99.00, "value": 15.00,
     "total_count": 1000, "user_limit": 1, "start_time": datetime(2026, 1, 1), "end_time": datetime(2026, 12, 31)},
    {"name": "全场满200减30", "coupon_type": "fixed", "threshold": 200.00, "value": 30.00,
     "total_count": 500, "user_limit": 3, "start_time": datetime(2026, 1, 1), "end_time": datetime(2026, 12, 31)},
    {"name": "茶叶类目8折券", "coupon_type": "percent", "threshold": 0, "value": 0.80,
     "total_count": 200, "user_limit": 1, "start_time": datetime(2026, 1, 1), "end_time": datetime(2026, 12, 31)},
    {"name": "满500减100", "coupon_type": "fixed", "threshold": 500.00, "value": 100.00,
     "total_count": 100, "user_limit": 1, "start_time": datetime(2026, 8, 1), "end_time": datetime(2026, 9, 30)},
]

# ── 示例用户 ─────────────────────────────────────────
DEMO_USERS = [
    {"username": "admin", "password": "admin123", "email": "admin@teashop.com", "role": "super_admin"},
    {"username": "operator1", "password": "op123456", "email": "op1@teashop.com", "role": "operator"},
    {"username": "viewer1", "password": "view1234", "email": "viewer@teashop.com", "role": "viewer"},
]

# ══════════════════════════════════════════════════════


def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_roles_and_permissions(db) -> dict:
    """创建角色+权限+角色权限关联，返回 {role_name: Role} 映射"""
    from app.services.auth_service import ROLE_PERMISSION_MAP

    # 权限
    perm_map = {}
    for resource, actions in PERMISSIONS.items():
        for action in actions:
            p = Permission(resource=resource, action=action)
            db.add(p)
            perm_map[f"{resource}:{action}"] = p
    db.flush()

    # 角色
    role_map = {}
    for name, desc in ROLES:
        r = Role(name=name, description=desc)
        db.add(r)
        role_map[name] = r
    db.flush()

    # 角色↔权限关联（运行时鉴权读 role_permissions 表）
    link_count = 0
    for role_name, perms in ROLE_PERMISSION_MAP.items():
        role = role_map.get(role_name)
        if not role:
            continue
        for perm_str in perms:
            p = perm_map.get(perm_str)
            if not p:
                resource, action = perm_str.split(":", 1)
                p = Permission(resource=resource, action=action)
                db.add(p)
                db.flush()
                perm_map[perm_str] = p
            db.add(RolePermission(role_id=role.id, permission_id=p.id))
            link_count += 1
    db.flush()

    print(f"  [OK] 创建 {len(perm_map)} 个权限, {len(role_map)} 个角色, {link_count} 条角色权限关联")
    return role_map


def seed_admin_users(db, role_map: dict) -> None:
    """创建管理员账户"""
    for u in DEMO_USERS:
        user = User(
            username=u["username"],
            password_hash=hash_password(u["password"]),
            email=u["email"],
            status="active",
        )
        db.add(user)
        db.flush()
        # 分配角色
        db.add(UserRole(user_id=user.id, role_id=role_map[u["role"]].id))
    print(f"  [OK] 创建 {len(DEMO_USERS)} 个管理员账户")


def seed_categories(db) -> dict:
    """创建类目树"""
    cat_map = {}
    for cid, name, parent_id, level, sort in CATEGORIES:
        cat = Category(id=cid, name=name, parent_id=parent_id, level=level, sort_order=sort)
        db.add(cat)
        cat_map[cid] = cat
    print(f"  [OK] 创建 {len(CATEGORIES)} 个类目")
    return cat_map


def seed_products(db) -> None:
    """创建示例商品（含SKU+库存+图片）"""
    total_skus = 0
    for pdata in DEMO_PRODUCTS:
        product = Product(
            spu_code=pdata["spu_code"],
            name=pdata["name"],
            subtitle=pdata["subtitle"],
            category_id=pdata["category_id"],
            brand=pdata["brand"],
            main_image=pdata["main_image"],
            description=pdata["description"],
            status=pdata["status"],
            min_price=min(s["price"] for s in pdata["skus"]),
            max_price=max(s["price"] for s in pdata["skus"]),
        )
        db.add(product)
        db.flush()

        # 图片
        for img in pdata["images"]:
            db.add(ProductImage(product_id=product.id, **img))

        # SKU + 库存
        for sdata in pdata["skus"]:
            sku = Sku(
                sku_code=sdata["sku_code"],
                product_id=product.id,
                spec_info=sdata["spec"],
                price=sdata["price"],
                original_price=sdata.get("original_price"),
                barcode=sdata.get("barcode"),
            )
            db.add(sku)
            db.flush()
            db.add(Inventory(sku_id=sku.id, quantity=sdata["stock"]))
            total_skus += 1

    print(f"  [OK] 创建 {len(DEMO_PRODUCTS)} 个商品, {total_skus} 个SKU")


def seed_coupons(db) -> None:
    """创建示例优惠券"""
    for cdata in DEMO_COUPONS:
        db.add(Coupon(**cdata))
    print(f"  [OK] 创建 {len(DEMO_COUPONS)} 张优惠券模板")


def seed_reviews(db) -> None:
    """创建示例评价数据"""
    reviews_data = [
        {"product_id": 1, "order_id": None, "user_id": 2, "rating": 5, "content": "龙井茶叶品质很好，冲泡后香气扑鼻，回甘明显。包装也很精美，送礼很合适。", "status": "approved"},
        {"product_id": 1, "order_id": None, "user_id": 2, "rating": 4, "content": "朋友推荐的龙井，味道确实不错，就是价格稍贵。", "status": "approved"},
        {"product_id": 2, "order_id": None, "user_id": 2, "rating": 5, "content": "大红袍岩韵十足，茶汤橙红透亮，入口醇厚顺滑，物有所值！", "status": "approved"},
        {"product_id": 3, "order_id": None, "user_id": 2, "rating": 5, "content": "普洱茶饼陈化得不错，金芽密布，冲泡后汤色红浓，口感醇厚回甘。", "status": "approved", "reply": "感谢您的认可！普洱茶越陈越香，建议在通风干燥处存放。"},
        {"product_id": 4, "order_id": None, "user_id": 2, "rating": 5, "content": "金骏眉品质很好，金毫明显，冲泡后蜜香浓郁，口感甜润。", "status": "approved"},
        {"product_id": 5, "order_id": None, "user_id": 2, "rating": 4, "content": "白毫银针外形美观，白毫披覆，口感清新淡雅，适合日常饮用。", "status": "approved"},
    ]
    for rv in reviews_data:
        existing = db.execute(select(Review).where(Review.product_id == rv["product_id"], Review.user_id == rv["user_id"])).scalar_one_or_none()
        if not existing:
            db.add(Review(**rv))
    db.commit()
    print("  Reviews seeded")


def reset_tables(db) -> None:
    """清空种子数据涉及的表"""
    tables = [
        "user_coupons", "coupons", "promotions",
        "inventory", "inventory_logs",
        "skus", "product_images", "products", "categories",
        "user_roles", "permissions", "roles",
        "addresses", "users", "reviews",
    ]
    for t in tables:
        db.execute(text(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE'))
    db.commit()
    print("[WARN] 已清空种子数据相关表")


if __name__ == "__main__":
    reset = "--reset" in sys.argv

    db = SessionLocal()
    try:
        if reset:
            reset_tables(db)

        print("开始填充种子数据...\n")

        role_map = seed_roles_and_permissions(db)
        seed_admin_users(db, role_map)
        seed_categories(db)
        seed_products(db)
        seed_coupons(db)
        seed_reviews(db)

        db.commit()
        print("\n[OK] 种子数据填充完成")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] 填充失败: {e}")
        raise
    finally:
        db.close()
