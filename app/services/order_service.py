"""订单服务：状态机流转 + 取消释放库存"""
import secrets
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.events.outbox import record_outbox
from app.models.tables import (
    Address,
    CartItem,
    Order,
    OrderItem,
    OrderLog,
    Payment,
    Product,
    Shipment,
    Sku,
    UserCoupon,
)
from app.repositories import (
    AddressRepository,
    InventoryRepository,
    OrderRepository,
    ProductRepository,
)
from app.services.async_bridge import async_adapter


class OrderService:
    VALID_TRANSITIONS = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["shipped", "cancelled"],
        "shipped": ["delivered", "completed", "cancelled"],
        "delivered": ["completed"],
    }

    @staticmethod
    def get_order_status(db: Session, order_no: str) -> dict:
        """根据订单号查询订单状态（供客服Agent工具调用）"""
        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单号 {order_no} 对应的订单"}
        return {
            "order_no": o.order_no,
            "order_status": o.order_status,
            "pay_status": o.pay_status,
            "total_amount": float(o.total_amount),
            "pay_amount": float(o.pay_amount),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
        }

    @staticmethod
    def get_order_by_no(db: Session, order_no: str) -> dict | None:
        """按订单号查询完整订单详情（商品/支付/物流/日志），供客服工具调用"""
        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return None
        return OrderService.get_order(db, o.id)

    @staticmethod
    async def create_order_async(
        db: AsyncSession,
        user_id: int,
        items: list[dict],
        address_id: int,
        remark: str | None = None,
        user_coupon_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        from app.services.coupon_service import CouponService
        from app.services.idempotency_service import begin_idempotent, complete_idempotent

        if idempotency_key:
            existing = await begin_idempotent(
                db, idempotency_key, "order.create", str(user_id),
            )
            if existing:
                return existing

        try:
            address_repo = AddressRepository(db)
            addr = await address_repo.get_by_id(address_id, user_id)
            if not addr:
                raise ValueError("收货地址不存在")

            merged: dict[int, int] = {}
            for it in items:
                qty = int(it["quantity"])
                if qty <= 0:
                    raise ValueError("购买数量必须为正数")
                merged[int(it["sku_id"])] = merged.get(int(it["sku_id"]), 0) + qty

            order_no = datetime.utcnow().strftime("%Y%m%d") + secrets.token_hex(5).upper()
            inventory_repo = InventoryRepository(db)
            product_repo = ProductRepository(db)
            order_items: list[dict] = []
            total_amount = 0.0
            for sku_id, qty in merged.items():
                sku = await product_repo.get_by_sku(sku_id)
                if not sku:
                    raise ValueError(f"SKU {sku_id} 不存在")
                product = await product_repo.get_by_id(sku.product_id)
                if not product or product.status != "online":
                    raise ValueError("商品已下架")
                await inventory_repo.deduct_atomic(
                    sku_id, qty, reason="order_create", ref_id=order_no
                )
                price = float(sku.price)
                subtotal = round(price * qty, 2)
                total_amount += subtotal
                order_items.append({
                    "sku": sku, "product": product,
                    "quantity": qty, "price": price, "subtotal": subtotal,
                })

            total_amount = round(total_amount, 2)
            discount_amount = 0.0
            if user_coupon_id:
                result = await CouponService.validate_coupon_async(
                    db, user_id, user_coupon_id, total_amount
                )
                if not result["valid"]:
                    raise ValueError(result["message"])
                discount_amount = result["discount"]

            pay_amount = max(round(total_amount - discount_amount, 2), 0)
            order = Order(
                order_no=order_no,
                user_id=user_id,
                address_id=address_id,
                total_amount=total_amount,
                pay_amount=pay_amount,
                discount_amount=discount_amount,
                order_status="pending",
                pay_status="unpaid",
                buyer_remark=remark,
            )
            db.add(order)
            await db.flush()

            if user_coupon_id:
                lock = await db.execute(
                    update(UserCoupon)
                    .where(
                        UserCoupon.id == user_coupon_id,
                        UserCoupon.user_id == user_id,
                        UserCoupon.status == "unused",
                    )
                    .values(status="used", used_at=datetime.utcnow(), order_id=order.id)
                )
                if lock.rowcount == 0:
                    raise ValueError("优惠券已被使用")

            payment_no = "PAY" + datetime.utcnow().strftime("%Y%m%d") + secrets.token_hex(4).upper()
            db.add(Payment(
                payment_no=payment_no,
                order_id=order.id,
                user_id=user_id,
                amount=pay_amount,
                channel="online",
                status="pending",
            ))

            for oi in order_items:
                db.add(OrderItem(
                    order_id=order.id,
                    sku_id=oi["sku"].id,
                    product_id=oi["product"].id,
                    product_name=oi["product"].name,
                    spec_info={"sku_name": oi["sku"].sku_code},
                    unit_price=oi["price"],
                    quantity=oi["quantity"],
                    total_price=oi["subtotal"],
                    image_url=oi["product"].main_image or "",
                ))

            await db.execute(
                delete(CartItem).where(
                    CartItem.user_id == user_id,
                    CartItem.sku_id.in_(list(merged.keys())),
                )
            )
            db.add(OrderLog(order_id=order.id, operator_id=user_id, action="create", detail="用户下单"))
            await record_outbox(
                db, "order", order.id, "order.created",
                {"order_id": order.id, "order_no": order.order_no, "user_id": user_id, "pay_amount": pay_amount},
            )
            await db.commit()
            result = {
                "id": order.id,
                "order_no": order.order_no,
                "pay_amount": float(pay_amount),
                "items": [{"sku_id": oi["sku"].id, "product_id": oi["product"].id} for oi in order_items],
            }
            if idempotency_key:
                await complete_idempotent(db, idempotency_key, result)
            return result
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def cancel_order_async(
        db: AsyncSession,
        order_id: int,
        reason: str | None = None,
        operator_id: int | None = None,
    ) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order:
            raise ValueError("订单不存在")
        await OrderService._transition_async(db, order, "cancelled", operator_id, reason)
        await record_outbox(db, "order", order.id, "order.cancelled", {"order_no": order.order_no, "reason": reason})
        await db.commit()
        return {"id": order.id, "order_status": order.order_status}

    @staticmethod
    async def confirm_receipt_async(db: AsyncSession, order_id: int, operator_id: int | None = None) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order:
            raise ValueError("订单不存在")
        if order.order_status == "shipped":
            await OrderService._transition_async(db, order, "delivered", operator_id)
        await OrderService._transition_async(db, order, "completed", operator_id)
        await db.commit()
        return {"id": order.id, "order_status": order.order_status}

    @staticmethod
    async def confirm_order_async(
        db: AsyncSession,
        order_id: int,
        operator_id: int | None = None,
    ) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order:
            raise ValueError("订单不存在")
        await OrderService._transition_async(db, order, "confirmed", operator_id)
        await db.commit()
        return {"id": order.id, "order_status": order.order_status}

    @staticmethod
    async def complete_order_async(
        db: AsyncSession,
        order_id: int,
        operator_id: int | None = None,
    ) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order:
            raise ValueError("订单不存在")
        await OrderService._transition_async(db, order, "completed", operator_id)
        await db.commit()
        return {"id": order.id, "order_status": order.order_status}

    @staticmethod
    async def ship_order_async(
        db: AsyncSession,
        order_id: int,
        carrier: str,
        tracking_no: str | None = None,
        operator_id: int | None = None,
    ) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order:
            raise ValueError("订单不存在")
        await OrderService._transition_async(db, order, "shipped", operator_id)
        address = None
        if order.address_id:
            address = await AddressRepository(db).get_by_id(order.address_id, order.user_id)
        shipment = Shipment(
            shipment_no=f"SHIP{secrets.token_hex(6).upper()}",
            order_id=order.id,
            carrier=carrier,
            tracking_no=tracking_no,
            status="shipped",
            receiver=address.receiver if address else "",
            receiver_phone=address.phone if address else "",
            address=(
                f"{address.province}{address.city}{address.district}{address.detail}"
                if address else ""
            ),
            shipped_at=datetime.utcnow(),
        )
        db.add(shipment)
        await record_outbox(
            db, "shipment", "pending", "shipment.created",
            {"order_id": order.id, "shipment_no": shipment.shipment_no, "tracking_no": tracking_no},
        )
        await db.commit()
        return {"id": order.id, "order_status": order.order_status, "shipment_no": shipment.shipment_no}

    @staticmethod
    async def _release_inventory_async(db: AsyncSession, order: Order) -> None:
        repo = OrderRepository(db)
        items = await repo.get_items(order.id)
        inv_repo = InventoryRepository(db)
        for item in items:
            await inv_repo.release_atomic(
                item.sku_id, item.quantity, reason="order_cancel", ref_id=order.order_no
            )

    @staticmethod
    async def _transition_async(
        db: AsyncSession,
        order: Order,
        to_status: str,
        operator_id: int | None = None,
        detail: str | None = None,
    ) -> None:
        valid = OrderService.VALID_TRANSITIONS.get(order.order_status, [])
        if to_status not in valid:
            raise ValueError(f"订单状态不能从 {order.order_status} 流转到 {to_status}")
        order.order_status = to_status
        now = datetime.utcnow()
        if to_status == "cancelled":
            order.cancelled_at = now
            await OrderService._release_inventory_async(db, order)
        elif to_status == "shipped":
            order.shipped_at = now
        elif to_status == "delivered":
            order.delivered_at = now
        elif to_status == "completed":
            order.completed_at = now
        db.add(OrderLog(order_id=order.id, operator_id=operator_id, action=to_status, detail=detail))

    @staticmethod
    async def list_orders_async(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        order_status: str | None = None,
        user_id: int | None = None,
    ) -> tuple[list[dict], int]:
        repo = OrderRepository(db)
        stmt = select(Order)
        if user_id:
            stmt = stmt.where(Order.user_id == user_id)
        if order_status:
            stmt = stmt.where(Order.order_status == order_status)
        rows, total = await repo.paginate(stmt, page, page_size, order_by=Order.id.desc())
        return [OrderService._order_summary(r) for r in rows], total

    @staticmethod
    async def get_order_detail_async(db: AsyncSession, order_id: int, user_id: int | None = None) -> dict:
        repo = OrderRepository(db)
        order = await repo.get_by_id(order_id)
        if not order or (user_id is not None and order.user_id != user_id):
            raise ValueError("订单不存在")
        items = await repo.get_items(order.id)
        item_data = [{
            "id": i.id,
            "product_id": i.product_id,
            "product_name": i.product_name,
            "sku_name": i.spec_info.get("sku_name", ""),
            "price": float(i.unit_price),
            "quantity": i.quantity,
            "image": i.image_url or "",
        } for i in items]
        addr = None
        if order.address_id:
            address = await AddressRepository(db).get_by_id(order.address_id, order.user_id)
            if address:
                addr = {
                    "receiver_name": address.receiver,
                    "receiver_phone": address.phone,
                    "province": address.province,
                    "city": address.city,
                    "district": address.district,
                    "detail": address.detail,
                }
        return {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.order_status,
            "pay_status": order.pay_status,
            "total_amount": float(order.total_amount),
            "items": item_data,
            "address": addr,
            "created_at": str(order.created_at),
            "paid_at": str(order.paid_at) if order.paid_at else None,
            "shipped_at": str(order.shipped_at) if order.shipped_at else None,
            "finished_at": str(order.completed_at) if order.completed_at else None,
        }

    @staticmethod
    def _order_summary(o: Order) -> dict:
        return {
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "total_amount": float(o.total_amount),
            "discount_amount": float(o.discount_amount),
            "pay_amount": float(o.pay_amount),
            "pay_status": o.pay_status,
            "order_status": o.order_status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }

    @staticmethod
    def create_order(db: Session, user_id: int, items: list[dict], address_id: int,
                     remark: str | None = None, user_coupon_id: int | None = None) -> dict:
        """创建订单（单事务：地址校验 → 原子扣库存 → 优惠券锁定 → 建单 → 清购物车）"""
        from app.services.coupon_service import CouponService
        from app.services.inventory_service import InventoryService

        if not items:
            raise ValueError("订单项不能为空")

        try:
            addr = db.execute(
                select(Address).where(Address.id == address_id, Address.user_id == user_id)
            ).scalar_one_or_none()
            if not addr:
                raise ValueError("收货地址不存在")

            # 合并同 SKU 项，校验数量
            merged: dict[int, int] = {}
            for it in items:
                qty = int(it["quantity"])
                if qty <= 0:
                    raise ValueError("购买数量必须为正数")
                merged[int(it["sku_id"])] = merged.get(int(it["sku_id"]), 0) + qty

            order_no = datetime.utcnow().strftime("%Y%m%d") + secrets.token_hex(5).upper()
            order_items = []
            total_amount = 0.0
            for sku_id, qty in merged.items():
                sku = db.execute(select(Sku).where(Sku.id == sku_id)).scalar_one_or_none()
                if not sku:
                    raise ValueError(f"SKU {sku_id} 不存在")
                product = db.execute(
                    select(Product).where(Product.id == sku.product_id)
                ).scalar_one_or_none()
                if not product or product.status != "online":
                    raise ValueError(f"商品「{product.name if product else sku.product_id}」已下架")

                InventoryService.deduct_atomic(db, sku_id, qty, reason="order_create", ref_id=order_no)

                price = float(sku.price)
                subtotal = round(price * qty, 2)
                total_amount += subtotal
                order_items.append({
                    "sku": sku, "product": product,
                    "quantity": qty, "price": price, "subtotal": subtotal,
                })

            total_amount = round(total_amount, 2)

            discount_amount = 0.0
            if user_coupon_id:
                result = CouponService.validate_coupon(db, user_id, user_coupon_id, total_amount)
                if not result["valid"]:
                    raise ValueError(result["message"])
                discount_amount = result["discount"]

            pay_amount = max(round(total_amount - discount_amount, 2), 0)
            order = Order(
                order_no=order_no,
                user_id=user_id,
                address_id=address_id,
                total_amount=total_amount,
                pay_amount=pay_amount,
                discount_amount=discount_amount,
                order_status="pending",
                pay_status="unpaid",
                buyer_remark=remark,
            )
            db.add(order)
            db.flush()

            if user_coupon_id:
                lock = db.execute(
                    update(UserCoupon)
                    .where(
                        UserCoupon.id == user_coupon_id,
                        UserCoupon.user_id == user_id,
                        UserCoupon.status == "unused",
                    )
                    .values(status="used", used_at=datetime.utcnow(), order_id=order.id)
                )
                if lock.rowcount == 0:
                    raise ValueError("优惠券已被使用")

            payment_no = "PAY" + datetime.utcnow().strftime("%Y%m%d") + secrets.token_hex(4).upper()
            db.add(Payment(
                payment_no=payment_no,
                order_id=order.id,
                user_id=user_id,
                amount=pay_amount,
                channel="online",
                status="pending",
            ))

            for oi in order_items:
                db.add(OrderItem(
                    order_id=order.id,
                    sku_id=oi["sku"].id,
                    product_id=oi["product"].id,
                    product_name=oi["product"].name,
                    spec_info={"sku_name": oi["sku"].sku_code},
                    unit_price=oi["price"],
                    quantity=oi["quantity"],
                    total_price=oi["subtotal"],
                    image_url=oi["product"].main_image or "",
                ))

            db.execute(
                delete(CartItem).where(
                    CartItem.user_id == user_id,
                    CartItem.sku_id.in_(list(merged.keys())),
                )
            )

            db.add(OrderLog(order_id=order.id, operator_id=user_id, action="create", detail="用户下单"))
            db.commit()
            return {
                "id": order.id,
                "order_no": order.order_no,
                "pay_amount": float(pay_amount),
                "items": [
                    {"sku_id": oi["sku"].id, "product_id": oi["product"].id}
                    for oi in order_items
                ],
            }
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def list_orders(db: Session, page: int = 1, page_size: int = 20,
                    keyword: str | None = None, order_status: str | None = None,
                    pay_status: str | None = None,
                    start_time: str | None = None, end_time: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Order)

        if keyword:
            query = query.where(Order.order_no.ilike(f"%{keyword}%"))
        if order_status:
            query = query.where(Order.order_status == order_status)
        if pay_status:
            query = query.where(Order.pay_status == pay_status)
        if start_time:
            query = query.where(Order.created_at >= datetime.fromisoformat(start_time))
        if end_time:
            query = query.where(Order.created_at <= datetime.fromisoformat(end_time))

        rows, total = paginate(db, query, page, page_size, order_by=Order.id.desc())

        result = []
        for o in rows:
            result.append({
                "id": o.id, "order_no": o.order_no, "user_id": o.user_id,
                "total_amount": float(o.total_amount),
                "discount_amount": float(o.discount_amount),
                "pay_amount": float(o.pay_amount),
                "pay_status": o.pay_status, "order_status": o.order_status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            })
        return result, total

    @staticmethod
    def get_order(db: Session, order_id: int) -> dict:
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")

        items = db.execute(select(OrderItem).where(OrderItem.order_id == o.id)).scalars().all()
        logs = db.execute(
            select(OrderLog).where(OrderLog.order_id == o.id).order_by(OrderLog.created_at.desc())
        ).scalars().all()
        payments = db.execute(select(Payment).where(Payment.order_id == o.id)).scalars().all()
        shipments = db.execute(select(Shipment).where(Shipment.order_id == o.id)).scalars().all()

        return {
            "id": o.id, "order_no": o.order_no, "user_id": o.user_id,
            "address_id": o.address_id,
            "total_amount": float(o.total_amount),
            "discount_amount": float(o.discount_amount),
            "pay_amount": float(o.pay_amount),
            "pay_status": o.pay_status, "order_status": o.order_status,
            "buyer_remark": o.buyer_remark,
            "items": [{
                "id": i.id, "product_name": i.product_name, "spec_info": i.spec_info,
                "unit_price": float(i.unit_price), "quantity": i.quantity,
                "total_price": float(i.total_price), "image_url": i.image_url,
            } for i in items],
            "payments": [{
                "id": p.id, "payment_no": p.payment_no, "amount": float(p.amount),
                "channel": p.channel, "status": p.status,
            } for p in payments],
            "shipments": [{
                "id": s.id, "shipment_no": s.shipment_no, "carrier": s.carrier,
                "tracking_no": s.tracking_no, "status": s.status,
                "receiver": s.receiver, "address": s.address,
            } for s in shipments],
            "logs": [{"action": l.action, "detail": l.detail, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs],
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
            "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
            "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
        }

    @staticmethod
    def _transition(db: Session, order: Order, to_status: str,
                    operator_id: int | None = None, detail: str | None = None) -> None:
        valid = OrderService.VALID_TRANSITIONS.get(order.order_status, [])
        if to_status not in valid:
            raise ValueError(f"订单状态不能从 {order.order_status} 流转到 {to_status}")

        order.order_status = to_status
        now = datetime.utcnow()
        if to_status == "cancelled":
            order.cancelled_at = now
            OrderService._release_inventory(db, order)
        elif to_status == "shipped":
            order.shipped_at = now
        elif to_status == "delivered":
            order.delivered_at = now
        elif to_status == "completed":
            order.completed_at = now

        db.add(OrderLog(order_id=order.id, operator_id=operator_id, action=to_status, detail=detail))
        db.commit()

    @staticmethod
    def _release_inventory(db: Session, order: Order) -> None:
        """取消订单时回补库存（原子操作 + 流水）"""
        from app.services.inventory_service import InventoryService

        items = db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all()
        for item in items:
            InventoryService.release_atomic(
                db, item.sku_id, item.quantity,
                reason="order_cancel", ref_id=order.order_no,
            )
        db.flush()

    @staticmethod
    def confirm_order(db: Session, order_id: int, operator_id: int | None = None) -> dict:
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")
        OrderService._transition(db, o, "confirmed", operator_id)
        return {"id": o.id, "order_status": o.order_status}

    @staticmethod
    def ship_order(db: Session, order_id: int, carrier: str, tracking_no: str | None = None,
                   operator_id: int | None = None) -> dict:
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")

        OrderService._transition(db, o, "shipped", operator_id)

        # 创建物流记录
        items = db.execute(select(OrderItem).where(OrderItem.order_id == o.id)).scalars().all()
        shipment_no = f"SHIP{secrets.token_hex(6).upper()}"
        shipment = Shipment(
            shipment_no=shipment_no,
            order_id=o.id,
            carrier=carrier,
            tracking_no=tracking_no,
            status="shipped",
            receiver="",  # 可从address表获取
            receiver_phone="",
            address="",
            shipped_at=datetime.utcnow(),
        )
        db.add(shipment)
        db.commit()
        return {"id": o.id, "order_status": o.order_status, "shipment_no": shipment_no}

    @staticmethod
    def cancel_order(db: Session, order_id: int, reason: str | None = None,
                     operator_id: int | None = None) -> dict:
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")
        OrderService._transition(db, o, "cancelled", operator_id, reason)
        from app.core.events import publish_sync
        publish_sync("order.cancelled", {"order_id": o.id, "order_no": o.order_no, "reason": reason or "user_cancel"})
        return {"id": o.id, "order_status": o.order_status}

    @staticmethod
    def complete_order(db: Session, order_id: int, operator_id: int | None = None) -> dict:
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")
        OrderService._transition(db, o, "completed", operator_id)
        return {"id": o.id, "order_status": o.order_status}

    @staticmethod
    def confirm_receipt(db: Session, order_id: int, operator_id: int | None = None) -> dict:
        """确认收货：已发货→已送达→已完成 的连续流转"""
        o = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not o:
            raise ValueError("订单不存在")
        if o.order_status == "shipped":
            OrderService._transition(db, o, "delivered", operator_id)
        OrderService._transition(db, o, "completed", operator_id)
        return {"id": o.id, "order_status": o.order_status}


OrderService.get_order_async = async_adapter(OrderService.get_order)
