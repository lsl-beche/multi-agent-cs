"""安全验收自动化检查（CI 门禁）"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, message: str) -> list[str]:
    return [] if condition else [message]


def main() -> int:
    problems: list[str] = []
    seed = (ROOT / "scripts" / "seed_data.py").read_text(encoding="utf-8")
    problems += check("admin123" not in seed, "种子数据仍包含弱口令 admin123")
    problems += check("op123456" not in seed, "种子数据仍包含弱口令 op123456")
    problems += check("view1234" not in seed, "种子数据仍包含弱口令 view1234")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    problems += check(".env\n" in gitignore or ".env" in gitignore, ".gitignore 未忽略 .env")
    problems += check("/models/\n" in gitignore, ".gitignore 未使用根目录 models 忽略规则")

    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    problems += check("Content-Security-Policy" in main, "未设置 CSP 安全响应头")
    quota = (ROOT / "app" / "core" / "quota.py").read_text(encoding="utf-8")
    problems += check("csagent:quota:llm:" in quota, "LLM 用户配额未实现")

    checks = [
        [sys.executable, "-m", "compileall", "-q", "app", "scripts"],
        [sys.executable, "-m", "ruff", "check", "app", "scripts", "tests"],
    ]
    for cmd in checks:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            problems.append(f"命令失败: {' '.join(cmd)} -> {result.stderr[:500]}")

    if problems:
        print("安全验收未通过：")
        for item in problems:
            print(f"- {item}")
        return 1
    print("安全验收通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
