"""每日支付对账（可 cron/任务调度执行）：
    python scripts/reconcile_payments.py [--window 24] [--strict]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tasks.reconcile_tasks import reconcile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, default=24, help="对账窗口（小时）")
    parser.add_argument("--strict", action="store_true", help="存在差异时返回非零退出码")
    args = parser.parse_args()
    report = reconcile(args.window)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (args.strict and not report["ok"]) else 0


if __name__ == "__main__":
    sys.exit(main())
