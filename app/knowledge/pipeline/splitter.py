"""文本分块（步骤二）：按段落分块，块大小 512 token，重叠 128 token

说明：当前 FAQ 是"一条问答一个文档"（不切分），
分块器预留给长文档（商品详情/客服手册）场景使用。
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter


def get_splitter(chunk_size: int = 512, chunk_overlap: int = 128) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],  # 中文友好分隔符
    )


def split_texts(texts: list[str]) -> list[str]:
    splitter = get_splitter()
    chunks: list[str] = []
    for text in texts:
        chunks.extend(splitter.split_text(text))
    return chunks
