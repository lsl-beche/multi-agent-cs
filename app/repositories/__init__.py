"""Repository 层：集中数据库访问，提升事务边界与可测试性"""

from app.repositories.core import (
    AddressRepository,
    BaseRepository,
    CartRepository,
    CouponRepository,
    IdempotencyRepository,
    InventoryRepository,
    OrderRepository,
    OutboxRepository,
    PaymentRepository,
    ProductRepository,
    RefundRepository,
    ReviewRepository,
    TicketRepository,
    UserRepository,
)

__all__ = [
    "AddressRepository",
    "BaseRepository",
    "CartRepository",
    "CouponRepository",
    "InventoryRepository",
    "IdempotencyRepository",
    "OrderRepository",
    "OutboxRepository",
    "PaymentRepository",
    "ProductRepository",
    "RefundRepository",
    "ReviewRepository",
    "TicketRepository",
    "UserRepository",
]
