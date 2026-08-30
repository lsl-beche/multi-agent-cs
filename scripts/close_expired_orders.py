"""手动触发：未支付订单超时自动关闭（也可由后端后台任务自动执行）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks.order_tasks import close_expired_orders

if __name__ == "__main__":
    n = close_expired_orders()
    print(f"已关闭超时未支付订单：{n} 单")
