"""购物车领域服务（原生异步）"""
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import CartItem
from app.repositories import CartRepository, ProductRepository


class CartService:
    @staticmethod
    async def get_cart(db: AsyncSession, user_id: int) -> list[dict]:
        repo = CartRepository(db)
        product_repo = ProductRepository(db)
        items = await repo.list_by_user(user_id)
        result = []
        for item in items:
            sku = await product_repo.get_by_sku(item.sku_id)
            product = await product_repo.get_by_id(sku.product_id) if sku else None
            result.append({
                "id": item.id,
                "product_id": product.id if product else 0,
                "product_name": product.name if product else "",
                "sku_id": item.sku_id,
                "sku_name": sku.sku_code if sku else "",
                "price": float(sku.price) if sku else 0,
                "quantity": item.quantity,
                "image": product.main_image or "",
                "selected": item.selected,
            })
        return result

    @staticmethod
    async def add(db: AsyncSession, user_id: int, sku_id: int, quantity: int = 1) -> None:
        repo = CartRepository(db)
        product_repo = ProductRepository(db)
        sku = await product_repo.get_by_sku(sku_id)
        if not sku:
            raise ValueError("SKU 不存在")
        existing = await repo.get_by_sku(user_id, sku_id)
        if existing:
            existing.quantity += quantity
        else:
            await repo.add(CartItem(user_id=user_id, sku_id=sku_id, quantity=quantity, selected=True))
        await repo.commit()

    @staticmethod
    async def update(db: AsyncSession, user_id: int, item_id: int, quantity: int) -> None:
        repo = CartRepository(db)
        item = await repo.get_by_id(item_id, user_id)
        if not item:
            raise ValueError("购物车项不存在")
        item.quantity = max(1, quantity)
        await repo.commit()

    @staticmethod
    async def remove(db: AsyncSession, user_id: int, item_id: int) -> None:
        repo = CartRepository(db)
        item = await repo.get_by_id(item_id, user_id)
        if not item:
            raise ValueError("购物车项不存在")
        await repo.delete(item)
        await repo.commit()

    @staticmethod
    async def select_all(db: AsyncSession, user_id: int, selected: bool) -> None:
        await db.execute(
            update(CartItem).where(CartItem.user_id == user_id).values(selected=selected)
        )
        await db.commit()

    @staticmethod
    async def select_one(db: AsyncSession, user_id: int, item_id: int, selected: bool) -> None:
        await db.execute(
            update(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id).values(selected=selected)
        )
        await db.commit()
