"""跨平台生成 Shared OpenAPI 类型：优先使用项目 venv，避免系统 Python 缺依赖。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    candidate = (
        ROOT / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else ROOT / ".venv" / "bin" / "python"
    )
    python_cmd = str(candidate if candidate.exists() else sys.executable)
    subprocess.run(
        [python_cmd, str(ROOT / "scripts" / "export_openapi.py")],
        cwd=ROOT, check=True,
    )
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    shared_dir = ROOT / "web" / "shared"
    subprocess.run(
        [
            npx,
            "openapi-typescript",
            str(ROOT / "docs" / "openapi.json"),
            "-o",
            str(ROOT / "web" / "shared" / "src" / "types" / "generated.ts"),
        ],
        cwd=shared_dir, check=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
