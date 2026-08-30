"""库存服务：查询/调整/预警 + 流水记录 + 原子扣减（防超卖）"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.pagination import paginate
from app.models.tables import Inventory, InventoryLog, Product, Sku


class InventoryService:

    @staticmethod
    def list_inventory(db: Session, page: int = 1, page_size: int = 20,
                       keyword: str | None = None, low_stock_only: bool = False) -> tuple[list[dict], int]:
        query = (
            select(Inventory, Sku, Product.name)
            .join(Sku, Sku.id == Inventory.sku_id)
            .join(Product, Product.id == Sku.product_id, isouter=True)
        )
        if low_stock_only:
            query = query.where(Inventory.quantity <= Inventory.safety_stock)
        if keyword:
            query = query.where(Sku.sku_code.ilike(f"%{keyword}%"))

        rows, total = paginate(db, query, page, page_size, order_by=Inventory.id.desc())

        result = []
        for inv, sku, product_name in rows:
            result.append({
                "id": inv.id, "sku_id": inv.sku_id,
                "sku_code": sku.sku_code if sku else "",
                "product_name": product_name or "",
                "spec_info": sku.spec_info if sku else {},
                "quantity": inv.quantity, "locked_quantity": inv.locked_quantity,
                "safety_stock": inv.safety_stock,
                "is_low": inv.quantity <= inv.safety_stock,
                "warehouse_id": inv.warehouse_id,
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
            })
        return result, total

    @staticmethod
    def deduct_atomic(db: Session, sku_id: int, quantity: int, reason: str, ref_id: str | None = None) -> bool:
        """原子扣减库存（条件UPDATE，并发安全，防超卖）

        单条 UPDATE 带 quantity >= :n 条件，0行受影响即表示库存不足。
        调用方需在事务内调用，失败时抛 ValueError。
        """
        if quantity <= 0:
            raise ValueError("扣减数量必须为正数")

        inv = db.execute(
            select(Inventory).where(Inventory.sku_id == sku_id)
        ).scalar_one_or_none()
        if not inv:
            raise ValueError("库存记录不存在")
        before = inv.quantity

        result = db.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id)
            .where(Inventory.quantity >= quantity)
            .values(quantity=Inventory.quantity - quantity)
        )
        if result.rowcount == 0:
            raise ValueError(f"库存不足：SKU {sku_id} 当前可用 {before}，需要 {quantity}")

        db.add(InventoryLog(
            sku_id=sku_id, change_qty=-quantity,
            before_qty=before, after_qty=before - quantity,
            reason=reason, ref_id=ref_id,
        ))
        return True

    @staticmethod
    def release_atomic(db: Session, sku_id: int, quantity: int, reason: str, ref_id: str | None = None) -> None:
        """原子回补库存（取消订单/退款成功后调用）"""
        if quantity <= 0:
            return
        inv = db.execute(
            select(Inventory).where(Inventory.sku_id == sku_id)
        ).scalar_one_or_none()
        if not inv:
            return
        before = inv.quantity

        db.execute(
            update(Inventory)
            .where(Inventory.sku_id == sku_id)
            .values(quantity=Inventory.quantity + quantity)
        )
        db.add(InventoryLog(
            sku_id=sku_id, change_qty=quantity,
            before_qty=before, after_qty=before + quantity,
            reason=reason, ref_id=ref_id,
        ))

    @staticmethod
    def adjust_inventory(db: Session, sku_id: int, change_qty: int, reason: str = "manual") -> dict:
        """管理后台手动调整库存（正数入库，负数出库）"""
        inv = db.execute(
            select(Inventory).where(Inventory.sku_id == sku_id)
        ).scalar_one_or_none()
        if not inv:
            raise ValueError("库存记录不存在")

        before = inv.quantity
        after = before + change_qty
        if after < 0:
            raise ValueError(f"库存不足，当前库存 {before}，无法扣减 {abs(change_qty)}")

        inv.quantity = after
        db.add(InventoryLog(
            sku_id=sku_id, change_qty=change_qty,
            before_qty=before, after_qty=after,
            reason=reason,
        ))
        db.commit()
        return {"sku_id": sku_id, "before": before, "after": after, "change": change_qty}

    @staticmethod
    def get_logs(db: Session, sku_id: int | None = None,
                 page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        query = select(InventoryLog)
        if sku_id:
            query = query.where(InventoryLog.sku_id == sku_id)

        rows, total = paginate(db, query, page, page_size, order_by=InventoryLog.id.desc())

        result = [{
            "id": l.id, "sku_id": l.sku_id, "change_qty": l.change_qty,
            "before_qty": l.before_qty, "after_qty": l.after_qty,
            "reason": l.reason, "ref_id": l.ref_id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in rows]
        return result, total
