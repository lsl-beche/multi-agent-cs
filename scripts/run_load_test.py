"""本地/CI 轻量压测包装：生成 CSV 结果供验收。"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--spawn-rate", type=int, default=5)
    parser.add_argument("--run-time", default="20s")
    args = parser.parse_args()
    csv_prefix = ROOT / "docs" / "load_test"
    cmd = [
        sys.executable, "-m", "locust",
        "-f", str(ROOT / "tests/load/locustfile.py"),
        "--host", args.host,
        "--headless",
        "-u", str(args.users),
        "-r", str(args.spawn_rate),
        "-t", args.run_time,
        "--csv", str(csv_prefix),
    ]
    print("运行:", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
