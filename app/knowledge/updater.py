"""知识库热更新：Webhook/管理接口 增删改知识条目，无需重启服务

能力：
- upsert：按问题"先删后插"实现幂等（防止重复提交产生重复向量）
- delete_by_question：按 metadata.question 精确删除
- handle_webhook：商品变更事件入口（目前为 TODO，预留事件分发）

演进：生产级接入 Kafka（商品/价格变更事件流）异步消费，
并配合 ingest_knowledge.py 的 --version 做知识灰度发布。
"""
from app.knowledge.vectordb import doc_id_for, get_vectorstore


class KnowledgeUpdater:
    def upsert(self, items: list[dict], version: str = "latest") -> int:
        """新增/更新知识条目（按问题先删后插，幂等）

        items 格式：[{"question":..., "answer":..., "category":...}]
        version：知识版本标签，配合 knowledge_version 做灰度发布。
        返回成功写入条数。
        """
        vs = get_vectorstore()
        texts: list[str] = []
        metadatas: list[dict] = []
        ids: list[str] = []
        for it in items:
            self.delete_by_question(it["question"])
            sid = doc_id_for(it["question"], it["answer"])
            texts.append(f"问题：{it['question']}\n答案：{it['answer']}")
            metadatas.append({
                "source_id": sid,
                "category": it.get("category", "general"),
                "question": it["question"],
                "version": version,
            })
            ids.append(sid)
        if texts:
            vs.add_texts(texts, metadatas=metadatas, ids=ids)
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
        payload = event.get("payload") or {}
        if event_type == "knowledge.upsert":
            count = self.upsert(payload.get("items", []), payload.get("version", "latest"))
            return {"handled": event_type, "status": "updated", "count": count}
        if event_type in ("product.updated", "product.created"):
            # 商品变更热更新：由业务网关把商品摘要转换为知识条目后调用
            items = payload.get("items") or []
            count = self.upsert(items, payload.get("version", "latest"))
            return {"handled": event_type, "status": "updated", "count": count, "note": "按 payload.items 增量更新"}
        if event_type == "product.offline":
            # 下架：按商品名/问题删除对应知识条目
            question = payload.get("question", "")
            deleted = self.delete_by_question(question) if question else 0
            return {"handled": event_type, "status": "deleted", "count": deleted}
        return {"handled": event_type, "status": "ignored"}

    # TODO: RabbitMQ消费者（aio-pika）：监听商品变更消息队列，调用 upsert/delete
