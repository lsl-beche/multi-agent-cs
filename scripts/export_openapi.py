"""导出 FastAPI OpenAPI 3.1 JSON，供前端自动生成类型"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def main() -> None:
    spec = app.openapi()
    output = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI written: {output}")


if __name__ == "__main__":
    main()
