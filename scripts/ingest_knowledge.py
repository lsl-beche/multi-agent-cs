"""知识库一键入库：采集 -> 清洗 -> 分块 -> 向量化 -> 写入向量库

用法：
    python scripts/ingest_knowledge.py [--raw-dir data/raw] [--append]

默认幂等重建：先清空向量库再全量入库，重复执行不会产生重复向量；
--append 用于增量追加（跳过清空）。

语料格式（data/raw/*.json）：
    [{"question": "如何退货", "answer": "支持7天无理由退货...", "category": "aftersale"}]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 允许从项目根目录直接运行

import chromadb

from app.config.settings import settings
from app.knowledge.pipeline.cleaner import clean_all
from app.knowledge.pipeline.collector import collect_all
from app.knowledge.vectordb import COLLECTION_NAME, get_vectorstore


def reset_collection() -> None:
    """删除并重建集合，实现幂等全量重建（Chroma 无 delete-all API）"""
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    try:
        client.delete_collection(COLLECTION_NAME)
        print("已清空旧知识库，开始全量重建...")
    except Exception:
        print("旧知识库不存在，直接全量重建")


def main() -> None:
    parser = argparse.ArgumentParser(description="知识库入库")
    parser.add_argument("--raw-dir", default="data/raw", help="原始语料目录")
    parser.add_argument("--append", action="store_true", help="增量追加（不清空旧数据）")
    parser.add_argument("--version", default="latest", help="知识版本标签（灰度发布用）")
    args = parser.parse_args()

    pairs = collect_all(args.raw_dir)
    if not pairs:
        print(f"未在 {args.raw_dir} 发现语料（.json），请先放入FAQ数据")
        return

    pairs = clean_all(pairs)
    print(f"清洗后剩余 {len(pairs)} 条问答对，开始向量化入库...")

    # FAQ问答对直接作为文档入库；长文档场景先调用 pipeline/splitter.py 分块
    if not args.append:
        reset_collection()  # 必须在 get_vectorstore() 之前执行，否则单例缓存旧集合
    vs = get_vectorstore()
    texts = [f"问题：{p['question']}\n答案：{p['answer']}" for p in pairs]
    metadatas = [{
        "category": p.get("category", "general"),
        "question": p["question"],
        "version": args.version,
    } for p in pairs]
    vs.add_texts(texts, metadatas=metadatas)
    print(f"入库完成，共 {len(texts)} 条")


if __name__ == "__main__":
    main()
