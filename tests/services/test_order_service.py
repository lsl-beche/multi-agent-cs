"""订单服务集成测试：事务、库存原子扣减和状态流转。"""
from decimal import Decimal

from sqlalchemy import select

from app.models.tables import Address, Inventory, Order, Product, Sku, User
from app.services.order_service import OrderService


async def _seed_order_data(async_db):
    user = User(
        username="buyer_test",
        password_hash="fake-hash",
        status="active",
    )
    async_db.add(user)
    await async_db.flush()

    address = Address(
        user_id=user.id,
        receiver="测试用户",
        phone="13800138000",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="测试路 1 号",
        is_default=True,
    )
    product = Product(
        spu_code="P-TEST-001",
        name="测试茶叶",
        status="online",
        min_price=Decimal("99.00"),
        max_price=Decimal("199.00"),
    )
    async_db.add_all([address, product])
    await async_db.flush()

    sku = Sku(
        sku_code="SKU-TEST-001",
        product_id=product.id,
        spec_info={"package": "250g"},
        price=Decimal("99.00"),
    )
    async_db.add(sku)
    await async_db.flush()

    inventory = Inventory(
        sku_id=sku.id,
        warehouse_id=1,
        quantity=10,
        safety_stock=1,
    )
    async_db.add(inventory)
    await async_db.commit()
    return user, address, product, sku, inventory


async def test_create_order_and_deduct_inventory(async_db):
    user, address, _product, sku, inventory = await _seed_order_data(async_db)

    result = await async_db.run_sync(
        lambda s: OrderService.create_order(
            s,
            user.id,
            [{"sku_id": sku.id, "quantity": 2}],
            address.id,
        )
    )

    assert result["order_no"]
    assert result["pay_amount"] == 198.0
    order = (await async_db.execute(select(Order).where(Order.id == result["id"]))).scalar_one()
    assert order.total_amount == Decimal("198.00")
    inv = (await async_db.execute(select(Inventory).where(Inventory.id == inventory.id))).scalar_one()
    assert inv.quantity == 8


async def test_create_order_rejects_insufficient_stock(async_db):
    user, address, _product, sku, _inventory = await _seed_order_data(async_db)

    try:
        await async_db.run_sync(
            lambda s: OrderService.create_order(
                s,
                user.id,
                [{"sku_id": sku.id, "quantity": 100}],
                address.id,
            )
        )
    except ValueError as exc:
        assert "库存不足" in str(exc)
    else:
        raise AssertionError("库存不足时应当抛出异常")


async def test_order_state_transition(async_db):
    user, address, _product, sku, _inventory = await _seed_order_data(async_db)
    created = await async_db.run_sync(
        lambda s: OrderService.create_order(
            s,
            user.id,
            [{"sku_id": sku.id, "quantity": 1}],
            address.id,
        )
    )
    order_id = created["id"]

    confirmed = await async_db.run_sync(
        lambda s: OrderService.confirm_order(s, order_id)
    )
    assert confirmed["order_status"] == "confirmed"

    cancelled = await async_db.run_sync(
        lambda s: OrderService.cancel_order(s, order_id, reason="test")
    )
    assert cancelled["order_status"] == "cancelled"
    inv = (await async_db.execute(select(Inventory).where(Inventory.sku_id == sku.id))).scalar_one()
    assert inv.quantity == 10
