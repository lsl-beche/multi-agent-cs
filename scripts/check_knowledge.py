"""知识库质量门禁：语料校验 + 重复检测 + 覆盖率报告（CI/发布前执行）"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def norm_key(q: str) -> str:
    return re.sub(r"\W+", "", q or "")


def main() -> int:
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    errors: list[str] = []
    seen: dict[str, str] = {}
    cat_cnt: Counter = Counter()
    total = 0
    for f in sorted(raw_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            errors.append(f"{f.name}: 顶层必须是数组")
            continue
        for item in data:
            q, a = item.get("question", ""), item.get("answer", "")
            if not q or not a:
                errors.append(f"{f.name}: 缺少 question/answer -> {q[:20]}")
                continue
            if len(a) < 20:
                errors.append(f"{f.name}: 答案过短 -> {q[:20]}")
            key = norm_key(q)
            if key in seen:
                errors.append(f"{f.name}: 与 {seen[key]} 重复 -> {q[:30]}")
            else:
                seen[key] = f.name
            cat_cnt[item.get("category", "general")] += 1
            total += 1
    print(f"语料总数: {total} | 类目数: {len(cat_cnt)}")
    for c, n in cat_cnt.most_common():
        print(f"  {c}: {n}")
    if errors:
        print(f"\n发现 {len(errors)} 个问题：")
        for e in errors[:20]:
            print("  -", e)
        return 1
    print("\n知识库质量检查通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
