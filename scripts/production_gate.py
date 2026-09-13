"""生产上线质量门禁：编译、测试、迁移、安全与 AI 评测（本地/CI 共用）。"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, cmd: list[str], report: dict, cwd: Path | None = None) -> bool:
    result = subprocess.run(
        cmd, cwd=cwd or ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    ok = result.returncode == 0
    report["checks"].append({
        "name": name, "ok": ok,
        "stdout": result.stdout[-1000:],
        "stderr": result.stderr[-2000:],
    })
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.80)
    parser.add_argument("--ci", action="store_true", help="CI 模式：跳过数据库/AI 模型依赖项")
    args = parser.parse_args()
    report = {"ok": True, "checks": []}
    python = sys.executable

    report["ok"] &= run("compile", [python, "-m", "compileall", "-q", "app", "scripts", "tests"], report)
    if not args.ci:
        report["ok"] &= run("alembic-head", [python, "-m", "alembic", "upgrade", "head"], report)
    if not args.skip_tests:
        report["ok"] &= run(
            "pytest",
            [python, "-m", "pytest", "tests/unit", "tests/integration/test_agent_mock.py", "-q"],
            report,
        )
    report["ok"] &= run("security", [python, "scripts/security_acceptance.py"], report)
    if not args.ci:
        report["ok"] &= run(
            "ai-golden",
            [python, "scripts/eval_dialogue.py", "--threshold", str(args.threshold)],
            report,
        )
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_cmd:
        report["ok"] &= run("admin-build", [npm_cmd, "run", "build"], report, ROOT / "web" / "admin")

    out = ROOT / "docs" / "production_gate_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gate report: {out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
