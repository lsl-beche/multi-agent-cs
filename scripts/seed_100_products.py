"""生成100个虚拟茶叶商品

用法：
    python scripts/seed_100_products.py           # 生成100个商品（不重复已存在的SPU）
    python scripts/seed_100_products.py --reset   # 清空后重新生成（⚠ 删除所有商品）
"""
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.core.db import SessionLocal
from app.models.tables import Category, Product, ProductImage, Sku, Inventory

# ══════════════════════════════════════════════════
# 茶叶品牌
# ══════════════════════════════════════════════════
BRANDS = [
    "茗韵", "天福", "八马", "大益", "正山堂", "竹叶青", "小罐茶", "武夷星",
    "徽六", "谢裕大", "卢正浩", "吴裕泰", "张一元", "七彩云南", "陈升号",
    "下关沱茶", "中茶", "勐库戎氏", "澜沧古茶", "雨林古茶坊",
]

# ══════════════════════════════════════════════════
# 茶叶名称库（按品类）
# ══════════════════════════════════════════════════
TEA_NAMES = {
    "绿茶": [
        "明前特级", "雨前特级", "雀舌", "毛尖", "翠芽", "银毫", "云雾茶", "炒青",
        "碧螺春", "黄山毛峰", "太平猴魁", "六安瓜片", "安吉白茶", "信阳毛尖",
        "都匀毛尖", "峨眉雪芽", "庐山云雾", "恩施玉露", "蒙顶甘露", "金奖惠明",
    ],
    "红茶": [
        "正山小种", "金骏眉", "祁门红茶", "滇红金芽", "川红工夫", "宜红工夫",
        "英德红茶", "九曲红梅", "宁红工夫", "政和工夫", "坦洋工夫", "白琳工夫",
        "古树滇红", "大金针", "红螺春", "凤凰红茶",
    ],
    "乌龙茶": [
        "铁观音", "大红袍", "凤凰单丛", "冻顶乌龙", "东方美人", "肉桂", "水仙",
        "白毫乌龙", "文山包种", "金萱乌龙", "阿里山茶", "杉林溪茶", "梨山茶",
        "漳平水仙", "永春佛手", "黄金桂",
    ],
    "白茶": [
        "白毫银针", "白牡丹", "贡眉", "寿眉", "老白茶", "花香白牡丹",
        "荒野白茶", "炭焙白茶", "陈皮白茶", "紧压白茶",
    ],
    "普洱": [
        "古树生茶", "古树熟茶", "宫廷普洱", "老班章", "冰岛古树", "易武正山",
        "昔归古树", "班章生态", "南糯山", "布朗山", "景迈山", "邦崴古树",
        "千家寨", "困鹿山", "蛮砖古树",
    ],
    "花茶": [
        "茉莉花茶", "桂花乌龙", "玫瑰红茶", "菊花普洱", "栀子花茶", "珠兰花茶",
        "玉兰花茶", "金银花茶", "梅花茶", "荷花茶",
    ],
    "养生茶": [
        "陈皮普洱", "小青柑", "大红柑", "柠檬红茶", "蜜桃乌龙", "桂花龙井",
        "玫瑰白茶", "红枣枸杞茶", "人参乌龙", "姜枣茶",
    ],
}

# ══════════════════════════════════════════════════
# 规格组合
# ══════════════════════════════════════════════════
SPEC_COMBOS = [
    [{"name": "规格", "value": "50g"  }, {"name": "包装", "value": "散装"}],
    [{"name": "规格", "value": "100g" }, {"name": "包装", "value": "散装"}],
    [{"name": "规格", "value": "100g" }, {"name": "包装", "value": "铁罐装"}],
    [{"name": "规格", "value": "150g" }, {"name": "包装", "value": "简易袋装"}],
    [{"name": "规格", "value": "150g" }, {"name": "包装", "value": "礼盒装"}],
    [{"name": "规格", "value": "200g" }, {"name": "包装", "value": "散装"}],
    [{"name": "规格", "value": "200g" }, {"name": "包装", "value": "铁罐装"}],
    [{"name": "规格", "value": "250g" }, {"name": "包装", "value": "散装"}],
    [{"name": "规格", "value": "250g" }, {"name": "包装", "value": "礼盒装"}],
    [{"name": "规格", "value": "357g" }, {"name": "包装", "value": "棉纸饼茶"}],
    [{"name": "规格", "value": "500g" }, {"name": "包装", "value": "散装"}],
    [{"name": "规格", "value": "500g" }, {"name": "包装", "value": "礼盒装"}],
    [{"name": "规格", "value": "8g×15泡" }, {"name": "包装", "value": "小泡装礼盒"}],
    [{"name": "规格", "value": "5g×20泡" }, {"name": "包装", "value": "小泡装铁盒"}],
    [{"name": "规格", "value": "3g×30泡" }, {"name": "包装", "value": "品鉴装"}],
]

# ══════════════════════════════════════════════════
# 描述模板
# ══════════════════════════════════════════════════
DESCRIPTIONS = {
    "绿茶": "<p>来自核心产区的优质绿茶，采摘于清明前，茶芽肥壮，白毫显露。干茶色泽翠绿，冲泡后汤色嫩绿明亮，香气清新高雅，带有豆香或板栗香。滋味鲜爽甘醇，回甘持久，叶底嫩绿匀整。</p><p>绿茶未经发酵，保留了茶叶中大量的天然物质，富含茶多酚、儿茶素和维生素C。</p>",
    "红茶": "<p>精选高山茶园优质鲜叶，经传统红茶工艺精制而成。干茶条索紧结，色泽乌润，金毫显露。冲泡后汤色红艳明亮，香气馥郁持久，带有蜜糖香或花果香。滋味醇厚甘甜，汤感顺滑。</p><p>红茶是全发酵茶，茶性温和，暖胃养胃，适合日常品饮。</p>",
    "乌龙茶": "<p>产自知名乌龙茶产区，采用传统摇青工艺制作。干茶条索紧结卷曲，色泽砂绿润泽。冲泡后汤色金黄明亮，香气高扬，有天然花香或果香。滋味醇厚甘鲜，回甘强烈，七泡犹有余香。</p><p>乌龙茶属于半发酵茶，兼具绿茶的清香和红茶的醇厚。</p>",
    "白茶": "<p>采摘于早春嫩芽，经自然萎凋、文火慢焙而成。干茶满披白毫，如银似雪。冲泡后汤色杏黄清澈，毫香清雅，带有淡淡花香。滋味清甜醇爽，毫味明显，经久耐泡。</p><p>白茶制作工艺最简，保留了茶叶最原始的风味，素有「一年茶、三年药、七年宝」之说。</p>",
    "普洱": "<p>精选云南大叶种晒青毛茶为原料，经传统工艺精制。干茶条索肥壮，色泽墨绿油润。冲泡后汤色橙黄透亮（生茶）或红浓明亮（熟茶），香气纯正高扬，带有花蜜香或陈香。滋味醇厚饱满，回甘生津，经久耐泡。</p><p>普洱茶越陈越香，具有独特的收藏价值。</p>",
    "花茶": "<p>以优质茶坯结合鲜花经传统窨制工艺而成。干茶外形匀整，花香与茶香完美融合。冲泡后汤色清澈明亮，花香鲜灵持久，滋味鲜醇回甘，花香茶韵协调。</p><p>花茶兼具茶的功效和花的芳香，是日常品饮与馈赠亲友的佳品。</p>",
    "养生茶": "<p>精选天然原料，科学配比，将茶与养生食材完美结合。冲泡后汤色红浓明亮，香气复合协调。滋味醇和甘润，口感丰富有层次。</p><p>适合注重健康生活的茶友，日常品饮温和不刺激。</p>",
}

STATUS = ["online", "online", "online", "online", "offline"]  # 80% 上架, 20% 下架


def get_categories(db):
    """获取所有类目，按 name 映射"""
    cats = db.query(Category).all()
    by_name = {c.name: c.id for c in cats}
    by_id = {c.id: c.name for c in cats}
    # 建立反向：子类目 name → 顶级类目 name
    name_to_top = {}
    for c in cats:
        if c.parent_id:
            top = by_id.get(c.parent_id, "")
            name_to_top[c.name] = top
        else:
            name_to_top[c.name] = c.name
    return by_name, name_to_top


def generate_spu_code(index: int) -> str:
    return f"SPU{20240001 + index:08d}"


def generate_sku_code(spu_code: str, spec_idx: int) -> str:
    return f"{spu_code}-SKU{spec_idx + 1:02d}"


def calculate_price(base_price: float, spec_combo: list[dict]) -> float:
    """根据规格计算价格"""
    multiplier = 1.0
    for s in spec_combo:
        if s["name"] == "规格":
            val = s["value"]
            if "50g" in val or "3g×" in val:
                multiplier = 0.3
            elif "100g" in val or "5g×" in val:
                multiplier = 0.5
            elif "150g" in val or "8g×" in val:
                multiplier = 0.75
            elif "200g" in val:
                multiplier = 1.0
            elif "250g" in val:
                multiplier = 1.2
            elif "357g" in val:
                multiplier = 1.5
            elif "500g" in val:
                multiplier = 2.0
    if any(s["value"] in ("礼盒装", "小泡装礼盒", "品鉴装") for s in spec_combo):
        multiplier *= 1.3
    return round(base_price * multiplier, 2)


def generate_products(db, category_map, name_to_top, count=100):
    """生成虚拟商品"""
    created = 0
    used_names = set()

    # 获取已有 SPU 编号
    existing_codes = {row[0] for row in db.query(Product.spu_code).all()}
    max_existing = 20240000
    for code in existing_codes:
        try:
            num = int(code[3:])
            max_existing = max(max_existing, num)
        except ValueError:
            pass

    start_num = max_existing + 1

    while created < count:
        # 随机选品类
        category_name = random.choice(list(TEA_NAMES.keys()))
        tea_names = TEA_NAMES[category_name]
        tea_name = random.choice(tea_names)
        brand = random.choice(BRANDS)
        full_name = f"{brand} {tea_name}"

        if full_name in used_names:
            continue
        used_names.add(full_name)

        # 判断属于哪个顶级类目
        top_category = name_to_top.get(category_name, category_name)
        cat_id = category_map.get(category_name)

        # 生成价格
        base_price = round(random.uniform(80, 800), 2)

        # 生成规格 SKU（1-3 个规格组合）
        num_skus = random.choice([1, 1, 2, 2, 3])  # 偏向 1-2 个规格
        spec_combos = random.sample(SPEC_COMBOS, min(num_skus, len(SPEC_COMBOS)))

        spu_code = generate_spu_code(start_num + created)
        status = random.choice(STATUS)
        subtitle = f"{brand}出品 · {tea_name} · {category_name}"

        product = Product(
            spu_code=spu_code,
            name=full_name,
            subtitle=subtitle,
            category_id=cat_id,
            brand=brand,
            main_image=f"/static/products/placeholder_{random.randint(1, 6)}.jpg",
            description=DESCRIPTIONS.get(category_name, DESCRIPTIONS["绿茶"]),
            status=status,
            min_price=0,
            max_price=0,
            total_sales=random.randint(0, 5000) if status == "online" else 0,
        )
        db.add(product)
        db.flush()

        # 添加 SKU
        prices = []
        for si, spec_combo in enumerate(spec_combos):
            sku_code = generate_sku_code(spu_code, si)
            price = calculate_price(base_price, spec_combo)
            original_price = round(price * random.uniform(1.2, 1.8), 2)
            prices.append(price)

            sku = Sku(
                sku_code=sku_code,
                product_id=product.id,
                spec_info=spec_combo,
                price=price,
                original_price=original_price,
                barcode=f"6{random.randint(900000000000, 999999999999)}",
                status="online",
            )
            db.add(sku)
            db.flush()

            # 库存
            stock_qty = random.randint(50, 2000)
            inventory = Inventory(
                sku_id=sku.id,
                warehouse_id=1,
                quantity=stock_qty,
                locked_quantity=0,
                safety_stock=random.randint(10, 50),
            )
            db.add(inventory)

        # 更新商品价格范围
        product.min_price = min(prices)
        product.max_price = max(prices)

        # 添加商品图片
        for img_idx in range(1, random.randint(2, 5)):
            img = ProductImage(
                product_id=product.id,
                url=f"/static/products/placeholder_{random.randint(1, 6)}.jpg",
                sort_order=img_idx,
                is_main=(img_idx == 1),
            )
            db.add(img)

        created += 1
        if created % 20 == 0:
            db.flush()
            print(f"  已生成 {created}/{count} 个商品...")

    db.commit()
    return created


def main():
    reset = "--reset" in sys.argv

    db = SessionLocal()
    try:
        # 确保类目存在
        existing_cats = db.query(Category).count()
        if existing_cats == 0:
            print("类目数据为空！请先运行 scripts/seed_data.py")
            return

        if reset:
            print("⚠ 清空所有商品、SKU、库存、商品图片...")
            db.query(Inventory).delete()
            db.query(Sku).delete()
            db.query(ProductImage).delete()
            db.query(Product).delete()
            db.execute(text("ALTER SEQUENCE products_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE skus_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE product_images_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE inventory_id_seq RESTART WITH 1"))
            db.commit()
            print("  已清空")

        category_map, name_to_top = get_categories(db)
        print(f"已加载 {len(category_map)} 个类目")
        print(f"可用品类: {', '.join(TEA_NAMES.keys())}")
        print()

        print("开始生成 100 个虚拟茶叶商品...")
        created = generate_products(db, category_map, name_to_top, count=100)
        print(f"\n✅ 完成！共生成 {created} 个商品")
        print(f"  访问管理后台查看: http://localhost:3000")
    finally:
        db.close()


if __name__ == "__main__":
    main()
