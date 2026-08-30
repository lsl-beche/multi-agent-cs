"""核心 Repository 实现（异步 SQLAlchemy 2.0）"""
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    Address,
    CartItem,
    Coupon,
    IdempotencyKey,
    Inventory,
    InventoryLog,
    Order,
    OrderItem,
    OutboxEvent,
    Payment,
    Product,
    Review,
    Ticket,
    User,
    UserCoupon,
)


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, statement: Any):
        return await self.session.execute(statement)

    async def scalar_one_or_none(self, statement: Any):
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def scalars(self, statement: Any):
        return (await self.session.execute(statement)).scalars().all()

    async def add(self, obj: Any) -> Any:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: Any) -> None:
        await self.session.delete(obj)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def paginate(self, query: Select, page: int = 1, page_size: int = 20, order_by: Any = None):
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0
        if order_by is not None:
            query = query.order_by(order_by)
        rows = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return rows, total


class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: int) -> User | None:
        return await self.scalar_one_or_none(select(User).where(User.id == user_id))

    async def get_by_username(self, username: str) -> User | None:
        return await self.scalar_one_or_none(select(User).where(User.username == username))

    async def create(self, username: str, password_hash: str, email: str | None = None,
                     phone: str | None = None) -> User:
        user = User(username=username, password_hash=password_hash, email=email, phone=phone)
        return await self.add(user)


class AddressRepository(BaseRepository):
    async def get_by_id(self, address_id: int, user_id: int) -> Address | None:
        return await self.scalar_one_or_none(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )

    async def list_by_user(self, user_id: int) -> list[Address]:
        return await self.scalars(
            select(Address).where(Address.user_id == user_id).order_by(
                Address.is_default.desc(), Address.id.desc()
            )
        )

    async def clear_default(self, user_id: int) -> None:
        await self.execute(update(Address).where(Address.user_id == user_id).values(is_default=False))


class CartRepository(BaseRepository):
    async def get_by_id(self, item_id: int, user_id: int) -> CartItem | None:
        return await self.scalar_one_or_none(
            select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
        )

    async def get_by_sku(self, user_id: int, sku_id: int) -> CartItem | None:
        return await self.scalar_one_or_none(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.sku_id == sku_id)
        )

    async def list_by_user(self, user_id: int) -> list[CartItem]:
        return await self.scalars(
            select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id.desc())
        )


class ProductRepository(BaseRepository):
    async def get_by_id(self, product_id: int) -> Product | None:
        return await self.scalar_one_or_none(select(Product).where(Product.id == product_id))

    async def get_by_sku(self, sku_id: int):
        from app.models.tables import Sku

        return await self.scalar_one_or_none(select(Sku).where(Sku.id == sku_id))


class InventoryRepository(BaseRepository):
    async def get_by_sku(self, sku_id: int) -> Inventory | None:
        return await self.scalar_one_or_none(select(Inventory).where(Inventory.sku_id == sku_id))

    async def deduct_atomic(self, sku_id: int, quantity: int, reason: str, ref_id: str | None = None) -> None:
        if quantity <= 0:
            raise ValueError("扣减数量必须为正数")
        inv = await self.get_by_sku(sku_id)
        if not inv:
            raise ValueError("库存记录不存在")
        before = inv.quantity
        result = await self.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id, Inventory.quantity >= quantity)
            .values(quantity=Inventory.quantity - quantity)
        )
        if result.rowcount == 0:
            raise ValueError(f"库存不足：SKU {sku_id} 当前可用 {before}，需要 {quantity}")
        self.session.add(InventoryLog(
            sku_id=sku_id, change_qty=-quantity,
            before_qty=before, after_qty=before - quantity,
            reason=reason, ref_id=ref_id,
        ))

    async def release_atomic(self, sku_id: int, quantity: int, reason: str, ref_id: str | None = None) -> None:
        if quantity <= 0:
            return
        inv = await self.get_by_sku(sku_id)
        if not inv:
            return
        before = inv.quantity
        await self.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id)
            .values(quantity=Inventory.quantity + quantity)
        )
        self.session.add(InventoryLog(
            sku_id=sku_id, change_qty=quantity,
            before_qty=before, after_qty=before + quantity,
            reason=reason, ref_id=ref_id,
        ))


class OrderRepository(BaseRepository):
    async def get_by_id(self, order_id: int) -> Order | None:
        return await self.scalar_one_or_none(select(Order).where(Order.id == order_id))

    async def get_by_no(self, order_no: str) -> Order | None:
        return await self.scalar_one_or_none(select(Order).where(Order.order_no == order_no))

    async def get_items(self, order_id: int) -> list[OrderItem]:
        return await self.scalars(select(OrderItem).where(OrderItem.order_id == order_id))


class PaymentRepository(BaseRepository):
    async def get_by_no(self, payment_no: str) -> Payment | None:
        return await self.scalar_one_or_none(select(Payment).where(Payment.payment_no == payment_no))

    async def get_last_by_order(self, order_id: int) -> Payment | None:
        return await self.scalar_one_or_none(
            select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc()).limit(1)
        )


class RefundRepository(BaseRepository):
    async def get_by_id(self, refund_id: int):
        from app.models.tables import Refund

        return await self.scalar_one_or_none(select(Refund).where(Refund.id == refund_id))


class CouponRepository(BaseRepository):
    async def get_by_id(self, coupon_id: int) -> Coupon | None:
        return await self.scalar_one_or_none(select(Coupon).where(Coupon.id == coupon_id))

    async def get_user_coupon(self, user_id: int, user_coupon_id: int) -> UserCoupon | None:
        return await self.scalar_one_or_none(
            select(UserCoupon).where(
                UserCoupon.id == user_coupon_id,
                UserCoupon.user_id == user_id,
            )
        )


class OutboxRepository(BaseRepository):
    async def add_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def pending(self, limit: int = 100) -> list[OutboxEvent]:
        from sqlalchemy import select

        return await self.scalars(
            select(OutboxEvent).where(OutboxEvent.status == "pending").order_by(OutboxEvent.id).limit(limit)
        )

    async def mark_published(self, event_id: int) -> None:
        from datetime import datetime, timezone

        from sqlalchemy import update

        await self.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status="published", published_at=datetime.now(timezone.utc))
        )

    async def mark_failed(self, event_id: int, error: str) -> None:
        from sqlalchemy import update

        await self.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status="failed", error=error[:1000])
        )


class IdempotencyRepository(BaseRepository):
    async def get(self, key: str) -> IdempotencyKey | None:
        return await self.scalar_one_or_none(select(IdempotencyKey).where(IdempotencyKey.key == key))

    async def create(self, key: str, scope: str, user_id: str, payload: dict, expires_at) -> IdempotencyKey:
        record = IdempotencyKey(
            key=key,
            scope=scope,
            user_id=user_id,
            payload=payload,
            expires_at=expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record


class ReviewRepository(BaseRepository):
    async def get_by_order_product(self, order_id: int, product_id: int) -> Review | None:
        return await self.scalar_one_or_none(
            select(Review).where(Review.order_id == order_id, Review.product_id == product_id)
        )

    async def list_product(self, product_id: int, page: int, page_size: int) -> tuple[list[Review], int]:

        query = select(Review).where(Review.product_id == product_id, Review.status == "approved")
        rows, total = await self._paginate(query, page, page_size, Review.created_at.desc())
        return rows, total

    async def _paginate(self, query, page: int, page_size: int, order_by):
        # Repository 内使用异步分页（同步 paginate 由服务层在需要时复用）
        from sqlalchemy import func
        from sqlalchemy import select as sa_select

        count_query = sa_select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0
        query = query.order_by(order_by)
        rows = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return rows, total


class TicketRepository(BaseRepository):
    async def get_by_id(self, ticket_id: str) -> Ticket | None:
        return await self.scalar_one_or_none(select(Ticket).where(Ticket.ticket_id == ticket_id))

    async def list(self, status: str | None = None) -> list[Ticket]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(100)
        if status:
            stmt = stmt.where(Ticket.status == status)
        return await self.scalars(stmt)
