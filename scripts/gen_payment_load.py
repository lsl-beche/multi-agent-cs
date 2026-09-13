"""模拟 1000 笔支付/退款流水（含边界场景），并写入渠道账本

目标：生成可复现的对账数据，跑 reconcile --strict 验证零差异。
用法：python scripts/gen_payment_load.py [--count 1000] [--days 2]
"""
import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.tables import ChannelLedger, Order, Payment, Refund


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()
    db = SessionLocal()
    created = 0
    # 找一个在售测试用户（避免外键问题）
    o = db.execute(select(Order).limit(1)).scalars().first()
    if not o:
        print("数据库中无订单，请先造一个测试订单")
        return 1
    uid = o.user_id
    now = datetime.utcnow()
    for i in range(args.count):
        order_no = f"SO{now.strftime('%Y%m%d')}{10000 + i}"
        # 幂等：跳过已存在
        if db.execute(select(Order).where(Order.order_no == order_no)).scalars().first():
            continue
        amount = round(random.uniform(10, 3000), 2)
        scenario = i % 10  # 0-7 支付成功；8 部分退款；9 支付成功+全额退款
        order = Order(order_no=order_no, user_id=uid, total_amount=amount, discount_amount=0,
                      pay_amount=amount, pay_status="paid", order_status="confirmed",
                      created_at=now - timedelta(hours=random.randint(1, 20)),
                      paid_at=now - timedelta(hours=random.randint(1, 20)))
        db.add(order)
        db.flush()
        pay_trade = f"LDG{now.strftime('%Y%m%d')}{i:06d}"
        pay = Payment(payment_no=f"PAYL{i:06d}", order_id=order.id, user_id=uid, amount=amount,
                      channel="sandbox", trade_no=pay_trade, status="paid",
                      paid_at=order.paid_at, created_at=order.created_at)
        db.add(pay)
        db.flush()
        db.add(ChannelLedger(ledger_date=order.paid_at, channel="sandbox", type="payment",
                             channel_trade_no=pay_trade, out_no=order_no,
                             amount=amount, status="paid", raw={"scenario": scenario}))
        if scenario in (8, 9) and scenario == 8:
            refund_amount = round(amount * 0.5, 2)
        elif scenario == 9:
            refund_amount = amount
        else:
            refund_amount = None
        if refund_amount:
            refund_no = f"RF{now.strftime('%Y%m%d')}{i:06d}"
            refund = Refund(refund_no=refund_no, payment_id=pay.id, order_id=order.id,
                            amount=refund_amount, reason="对账测试", status="completed",
                            created_at=now - timedelta(hours=1), completed_at=now)
            db.add(refund)
            order.pay_status = "refunded"
            db.add(ChannelLedger(ledger_date=now, channel="sandbox", type="refund",
                                 channel_trade_no=f"R{pay_trade}", out_no=order_no,
                                 amount=refund_amount, status="refunded",
                                 raw={"scenario": scenario}))
        created += 1
        if created % 200 == 0:
            db.commit()
            print(f"  已生成 {created}")
    db.commit()
    print(f"共生成 {created} 笔（含部分退款/全额退款/边界场景）")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
