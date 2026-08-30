"""知识库热更新：Webhook/管理接口 增删改知识条目，无需重启服务

能力：
- upsert：按问题"先删后插"实现幂等（防止重复提交产生重复向量）
- delete_by_question：按 metadata.question 精确删除
- handle_webhook：商品变更事件入口（目前为 TODO，预留事件分发）

演进：生产级接入 Kafka（商品/价格变更事件流）异步消费，
并配合 ingest_knowledge.py 的 --version 做知识灰度发布。
"""
from app.knowledge.vectordb import get_vectorstore


class KnowledgeUpdater:
    def upsert(self, items: list[dict]) -> int:
        """新增/更新知识条目（按问题先删后插，幂等）

        items 格式：[{"question":..., "answer":..., "category":...}]
        返回成功写入条数。
        """
        vs = get_vectorstore()
        texts: list[str] = []
        metadatas: list[dict] = []
        for it in items:
            self.delete_by_question(it["question"])
            texts.append(f"问题：{it['question']}\n答案：{it['answer']}")
            metadatas.append({"category": it.get("category", "general"), "question": it["question"]})
        if texts:
            vs.add_texts(texts, metadatas=metadatas)
        return len(texts)

    def delete_by_question(self, question: str) -> int:
        """按问题删除知识条目（Chroma 按 metadata 精确删除）"""
        try:
            vs = get_vectorstore()
            vs._collection.delete(where={"question": question})
            return 1
        except Exception:
            return 0

    async def handle_webhook(self, event: dict) -> dict:
        """处理商品变更Webhook事件：{"type": "product.updated", "payload": {...}}"""
        event_type = event.get("type", "")
        # TODO: 按事件类型分发：商品更新 -> 重建对应向量；商品下架 -> 删除向量
        return {"handled": event_type, "status": "TODO"}

    # TODO: RabbitMQ消费者（aio-pika）：监听商品变更消息队列，调用 upsert/delete
