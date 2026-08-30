"""物流服务：发货列表 + 轨迹更新"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Order, Shipment


class ShipmentService:

    @staticmethod
    def get_shipment_by_order_no(db: Session, order_no: str) -> dict:
        """按订单号查询发货单与物流状态（客服工具用）"""
        o = db.execute(select(Order).where(Order.order_no == order_no)).scalar_one_or_none()
        if not o:
            return {"error": "not_found", "message": f"未找到订单 {order_no}"}
        rows = db.execute(
            select(Shipment).where(Shipment.order_id == o.id).order_by(Shipment.id.desc())
        ).scalars().all()
        return {
            "order_no": order_no,
            "shipments": [{
                "shipment_no": s.shipment_no,
                "carrier": s.carrier,
                "tracking_no": s.tracking_no,
                "status": s.status,
                "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
                "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
            } for s in rows],
        }

    @staticmethod
    def list_shipments(db: Session, page: int = 1, page_size: int = 20,
                       order_id: int | None = None,
                       status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(Shipment)
        if order_id:
            query = query.where(Shipment.order_id == order_id)
        if status:
            query = query.where(Shipment.status == status)

        rows, total = paginate(db, query, page, page_size, order_by=Shipment.id.desc())

        result = [{
            "id": s.id, "shipment_no": s.shipment_no, "order_id": s.order_id,
            "carrier": s.carrier, "tracking_no": s.tracking_no, "status": s.status,
            "receiver": s.receiver, "receiver_phone": s.receiver_phone,
            "address": s.address,
            "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
            "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        } for s in rows]
        return result, total

    @staticmethod
    def update_tracking(db: Session, shipment_id: int, tracking_no: str,
                        carrier: str | None = None) -> dict:
        s = db.execute(select(Shipment).where(Shipment.id == shipment_id)).scalar_one_or_none()
        if not s:
            raise ValueError("物流记录不存在")
        s.tracking_no = tracking_no
        if carrier:
            s.carrier = carrier
        db.commit()
        return {"id": s.id, "tracking_no": s.tracking_no, "carrier": s.carrier}
