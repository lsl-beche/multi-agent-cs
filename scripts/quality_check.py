"""客服会话质检 v1：扫描最近会话，输出基础质量报告

指标：转人工率 / 平均轮数 / 兜底话术占比 / 空回复占比 / 合规拦截数
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import Conversation, MessageRecord, Ticket

FALLBACK_MARKERS = ("抱歉，暂时无法回答", "抱歉，当前回复较慢", "回复超时", "无法回复")


def run(days: int = 1) -> dict:
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        convs = db.execute(
            select(Conversation).where(Conversation.created_at >= since)
        ).scalars().all()
        stats = {
            "sessions": len(convs),
            "total_messages": 0,
            "avg_turns": 0.0,
            "fallback_replies": 0,
            "empty_replies": 0,
            "human_handoffs": 0,
            "compliance_blocks": 0,
        }
        turn_counter = Counter()
        fallback_counter = 0
        empty_counter = 0
        for conv in convs:
            msgs = db.execute(
                select(MessageRecord).where(MessageRecord.conversation_id == conv.id)
            ).scalars().all()
            user_turns = sum(1 for m in msgs if m.role == "user")
            turn_counter[conv.session_id] = user_turns
            stats["total_messages"] += len(msgs)
            for m in msgs:
                if m.role != "assistant":
                    continue
                content = m.content or ""
                if any(k in content for k in FALLBACK_MARKERS):
                    fallback_counter += 1
                if not content.strip():
                    empty_counter += 1
        tickets = db.execute(
            select(Ticket).where(Ticket.created_at >= since)
        ).scalars().all()
        stats["human_handoffs"] = len(tickets)
        stats["fallback_replies"] = fallback_counter
        stats["empty_replies"] = empty_counter
        stats["compliance_blocks"] = sum(1 for t in tickets if t.category == "compliance")
        if turn_counter:
            stats["avg_turns"] = round(sum(turn_counter.values()) / len(turn_counter), 2)
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    report = run(days)
    print(json.dumps(report, ensure_ascii=False, indent=2))
