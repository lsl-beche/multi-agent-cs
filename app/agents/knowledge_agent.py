"""知识检索Agent（RAG）：意图已由Supervisor判定为知识类，直接预检索+单次LLM生成

相比旧的 tool_call_loop 方案（LLM先决策是否检索、再生成，实测工具决策轮耗时15-30s），
本实现省去工具决策轮：知识类意图必然需要知识库内容，预检索结果直接注入 prompt，
LLM 只做一轮内容生成。
"""
import re
import time

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent, _strip_think_tags
from app.agents.graphs.state import AgentState
from app.knowledge.retriever import KnowledgeRetriever
from app.tools.product_tools import check_stock, search_product
from app.tools.review_tools import search_reviews

from loguru import logger

perf_logger = logger.bind(name="perf")


class KnowledgeAgent(BaseAgent):
    name = "knowledge_agent"
    description = "基于知识库回答茶叶品类、冲泡、保存、品鉴、健康类咨询"
    system_prompt = (
        "你是一家高端茶叶店铺的资深茶艺客服。请依据【知识库检索结果】回答用户问题，"
        "知识库没有的信息不要编造；可以在不改变事实的前提下组织语言，使回答更友好、更专业。"
        "若知识库内容与问题无关，礼貌告知用户并引导其补充描述或转人工。"
        "回答尽量简洁，控制在200字以内。"
    )

    def register_tools(self) -> list[BaseTool]:
        # 说明：本地模式走"规则预检索 + 单次 LLM 生成"（省去工具决策轮，实测快 15-30s）；
        # 这里的工具是给云端大模型的自主动 tool-calling 模式用的
        return [search_product, check_stock, search_reviews]

    async def run(self, state: AgentState) -> dict:
        """知识问答节点（RAG 直答模式）

        流程（为降低延迟专门优化，不再让 LLM 决定是否检索）：
        1. 预检索：KnowledgeRetriever 从 500 条 FAQ 中语义召回 top_k 条
        2. 上下文增强：库存/评价类问题额外注入商品工具结果
        3. 单次 LLM 生成：把"用户问题 + 知识库检索结果"交给 LLM 组织答复

        相比通用 tool-calling 的优点：
        - 知识类意图必然需要知识库，预检索避免一次"是否检索"的决策轮
        - 生成阶段只有一轮，CPU 推理延迟大幅下降
        """
        last = state["messages"][-1]
        query = last.content if hasattr(last, "content") else str(last)

        # ① 预检索：直接检索知识库（top_k=2，向量召回 + 词法 RRF 融合）
        t0 = time.perf_counter()
        docs = KnowledgeRetriever(top_k=2).retrieve(query)
        perf_logger.info(f"[knowledge_agent] preretrieve: {(time.perf_counter() - t0) * 1000:.0f}ms, results={len(docs)}")

        # ② 组装系统提示词：角色设定 + 防思考指令
        system_content = self.system_prompt + "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"

        # ③ 规则增强：库存/现货类问题直接查商品库存
        #    （本地模型不自主调工具，所以在规则层显式调用并把结果注入上下文）
        if any(k in query for k in ("库存", "现货", "有货", "还有货", "缺货")):
            try:
                res = await search_product.ainvoke({"keyword": query})
                system_content += f"\n\n【商品库存信息】{res}"
            except Exception:
                pass

        # ④ 规则增强：评价/口碑类问题检索已通过评价（自动清洗提问词，提高命中率）
        if any(k in query for k in ("评价", "口碑", "好评", "怎么样")):
            try:
                kw = re.sub(r"(评价|口碑|好评|怎么样|如何|觉得|的|吗|\?|？)", "", query).strip()
                res = await search_reviews.ainvoke({"keyword": kw or query})
                system_content += f"\n\n【用户评价】{res}"
            except Exception:
                pass

        if docs:
            # 瘦上下文：只取FAQ"答案"部分并截断（问题文本与用户问题重复，浪费prefill），
            # CPU prefill约33 token/s，每省1 token≈30ms
            parts = []
            for d in docs:
                content = d.page_content
                # 语料格式为"问题：X\n答案：Y"，只保留答案部分，减少提示词长度
                if "答案：" in content:
                    content = content.split("答案：", 1)[1]
                parts.append(content[:150])
            context = "\n\n---\n\n".join(parts)
            system_content += "\n\n【知识库检索结果】\n" + context

        # ⑤ 消息组装：系统提示（含知识库上下文）+ 对话历史 + 当前问题
        messages = [SystemMessage(content=system_content)] + list(state["messages"])

        # ⑥ 单次 LLM 生成客服话术
        t0 = time.perf_counter()
        resp = await self.llm.ainvoke(messages)
        perf_logger.info(f"[knowledge_agent] LLM generation: {(time.perf_counter() - t0) * 1000:.0f}ms, answer_len={len(resp.content or '')}")

        # 清洗思考标签（Qwen3 可能仍输出空 <think></think> 包壳）
        content = _strip_think_tags(resp.content or "")

        # ⑦ 空回答防护：本地小模型可能把 token 预算全耗在思考链上，
        #    导致 content 为空；重试一次并强制"直接输出答案"
        if not content:
            perf_logger.warning(f"[knowledge_agent] empty answer, retry once (t_llm={t_llm * 1000:.0f}ms)")
            t0 = time.perf_counter()
            retry_messages = [
                SystemMessage(content=system_content + "\n\n直接输出最终答案，禁止输出<think>推理过程。"),
                *state["messages"],
            ]
            resp2 = await self.llm.ainvoke(retry_messages)
            perf_logger.info(f"[knowledge_agent] LLM retry: {(time.perf_counter() - t0) * 1000:.0f}ms, answer_len={len(resp2.content or '')}")
            content = _strip_think_tags(resp2.content or "")

        return {"messages": [AIMessage(content=content or "抱歉，暂时无法回答。")]}
