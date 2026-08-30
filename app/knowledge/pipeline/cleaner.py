"""数据清洗（步骤一/二）：去 HTML 标签、规范化、去重

流水线（clean_all）：
1. 规范化：去 HTML/多余空白，保留中文标点
2. 过滤：空问题或空答案丢弃
3. 去重：按"忽略标点的规范化问题文本"保留首次出现

TODO：语义级去重（embedding 相似度合并"如何退货/退换货流程"等近似表述）。
"""
import re


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def normalize(text: str) -> str:
    """文本规范化：去多余空白与特殊符号"""
    text = strip_html(text)
    text = re.sub(r"[\r\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def dedup(pairs: list[dict]) -> list[dict]:
    """按问题文本去重（保留首次出现）"""
    seen: set[str] = set()
    result: list[dict] = []
    for item in pairs:
        key = re.sub(r"\W+", "", item["question"])  # 忽略标点差异
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def clean_all(pairs: list[dict]) -> list[dict]:
    """完整清洗流水线"""
    cleaned = [
        {**item, "question": normalize(item["question"]), "answer": normalize(item["answer"])}
        for item in pairs
    ]
    cleaned = [item for item in cleaned if item["question"] and item["answer"]]
    # TODO: 语义级去重（Embedding相似度合并“如何退货”与“退换货流程”等相似表述）
    return dedup(cleaned)
