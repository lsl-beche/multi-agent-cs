"""工单相关工具：创建售后工单

当前为"生成工单号 + 返回提示"的占位实现；
TODO(生产)：持久化到 tickets 表并推送售后系统/通知管理员。
"""
import uuid

from langchain_core.tools import tool

from app.tools.registry import register


@tool
def create_ticket(category: str, description: str, order_id: str = "") -> str:
    """创建售后工单：当用户需要人工处理售后问题时使用。
    参数：category 工单类型（如 return/exchange/complaint），description 问题描述，order_id 关联订单号（可选）。"""
    ticket_id = f"TK{uuid.uuid4().hex[:12].upper()}"
    # TODO: 持久化到 PostgreSQL（models/tables.py 的 Ticket 表）并通知售后系统
    return f"工单创建成功，工单号：{ticket_id}（类型：{category}）。售后专员将在24小时内处理。"


register(create_ticket)
