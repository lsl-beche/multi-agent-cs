"""数据报表服务：销售统计 + CS客服数据"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.tables import Conversation, CsatScore, MessageRecord, Order, Payment, Ticket


class ReportService:

    @staticmethod
    def sales_summary(db: Session, period: str = "today") -> dict:
        """period: today / yesterday / week / month"""
        now = datetime.utcnow()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "yesterday":
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 订单统计
        orders = db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(func.sum(Order.pay_amount), 0).label("total_amount"),
            ).where(Order.created_at >= start)
        ).one()

        # 各状态订单数
        status_rows = db.execute(
            select(Order.order_status, func.count(Order.id))
            .where(Order.created_at >= start)
            .group_by(Order.order_status)
        ).all()
        status_map = {row[0]: row[1] for row in status_rows}

        # 支付统计
        paid_rows = db.execute(
            select(
                func.count(Payment.id).label("paid_count"),
                func.coalesce(func.sum(Payment.amount), 0).label("paid_amount"),
            ).where(Payment.status == "success", Payment.created_at >= start)
        ).one()

        return {
            "period": period,
            "total_orders": orders.total_orders,
            "total_amount": float(orders.total_amount),
            "pending": status_map.get("pending", 0),
            "confirmed": status_map.get("confirmed", 0),
            "shipped": status_map.get("shipped", 0),
            "delivered": status_map.get("delivered", 0),
            "completed": status_map.get("completed", 0),
            "cancelled": status_map.get("cancelled", 0),
            "paid_count": paid_rows.paid_count,
            "paid_amount": float(paid_rows.paid_amount),
        }

    @staticmethod
    def cs_agent_dashboard(db: Session, period: str = "today") -> dict:
        """CS Agent 数据大屏"""
        now = datetime.utcnow()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 会话统计
        conv_total = db.execute(
            select(func.count(Conversation.id)).where(Conversation.created_at >= start)
        ).scalar() or 0

        conv_active = db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.status == "active", Conversation.created_at >= start)
        ).scalar() or 0

        # 工单统计
        ticket_total = db.execute(
            select(func.count(Ticket.id)).where(Ticket.created_at >= start)
        ).scalar() or 0

        ticket_pending = db.execute(
            select(func.count(Ticket.id))
            .where(Ticket.status == "pending", Ticket.created_at >= start)
        ).scalar() or 0

        # CSAT
        csat_rows = db.execute(
            select(
                func.count(CsatScore.id).label("total"),
                func.coalesce(func.avg(CsatScore.rating), 0).label("avg_rating"),
            ).where(CsatScore.created_at >= start)
        ).one()

        handoff_rate = 0.0
        if conv_total > 0:
            handoff_rate = round(ticket_total / conv_total * 100, 1)

        # 平均轮数 / 兜底回复数（AI 质量）
        msg_rows = db.execute(
            select(
                func.count(MessageRecord.id).label("cnt"),
                func.count(func.distinct(MessageRecord.conversation_id)).label("convs"),
            ).where(MessageRecord.created_at >= start)
        ).one()
        fallback_rows = db.execute(
            select(func.count(MessageRecord.id)).where(
                MessageRecord.created_at >= start,
                MessageRecord.role == "assistant",
                MessageRecord.content.like("%抱歉，暂时无法回答%"),
            )
        ).scalar() or 0
        avg_turns = 0.0
        if msg_rows.convs:
            avg_turns = round(msg_rows.cnt / msg_rows.convs, 2)
        ai_resolved = max(0, conv_total - ticket_total)
        ai_resolution_rate = round(ai_resolved / conv_total * 100, 1) if conv_total else 0.0

        # LLM 成本估算（从 Prometheus token 计数读取）
        llm_cost = 0.0
        try:
            from prometheus_client import REGISTRY
            tokens = float(REGISTRY.get_sample_value("csagent_llm_tokens_total") or 0)
            llm_cost = round(tokens / 1000 * settings.llm_cost_per_1k_tokens, 4)
        except Exception:
            pass

        return {
            "period": period,
            "total_conversations": conv_total,
            "active_conversations": conv_active,
            "total_tickets": ticket_total,
            "pending_tickets": ticket_pending,
            "handoff_rate": handoff_rate,
            "csat_total": csat_rows.total,
            "csat_avg": round(float(csat_rows.avg_rating), 2),
            "avg_turns": avg_turns,
            "fallback_replies": fallback_rows,
            "ai_resolved_sessions": ai_resolved,
            "ai_resolution_rate": ai_resolution_rate,
            "llm_cost_estimate": llm_cost,
        }
