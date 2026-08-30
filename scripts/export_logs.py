"""未解决问题导出：供每周知识库迭代（对应7.2 知识库迭代）

用法：
    python scripts/export_logs.py [--output data/processed/unresolved.csv]
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="导出未解决问题")
    parser.add_argument("--output", default="data/processed/unresolved.csv")
    args = parser.parse_args()

    # TODO: 从PostgreSQL查询 need_human=True 或低满意度会话的用户提问
    rows: list[dict] = []

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "question", "intent", "created_at"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"已导出 {len(rows)} 条未解决问题 -> {output}")


if __name__ == "__main__":
    main()
