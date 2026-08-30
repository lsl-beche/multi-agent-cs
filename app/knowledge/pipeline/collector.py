"""数据采集（步骤一）：历史客服对话、商品文档、客服手册、FAQ 问答对

当前仅实现 FAQ 采集（data/raw/*.json，数组格式）；
后续可扩展 CSV/Markdown/历史对话解析，统一由 collect_all 聚合。
"""
import json
from pathlib import Path


def load_faq(path: str | Path) -> list[dict]:
    """加载FAQ问答对，JSON格式：[{"question": "...", "answer": "...", "category": "..."}]"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [item for item in data if item.get("question") and item.get("answer")]


def load_conversations(path: str | Path) -> list[dict]:
    """从历史客服对话中提取高质量问答对"""
    # TODO: 解析对话记录，按会话切分并提取 Q->A 对
    return []


def collect_all(raw_dir: str | Path = "data/raw") -> list[dict]:
    """扫描原始语料目录，聚合全部FAQ数据"""
    raw_path = Path(raw_dir)
    pairs: list[dict] = []
    for file in sorted(raw_path.glob("*.json")):
        pairs.extend(load_faq(file))
    # TODO: 支持 .csv / .docx / .md 格式的商品文档与客服手册
    return pairs
