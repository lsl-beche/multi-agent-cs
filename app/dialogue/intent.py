"""意图识别：12 类客服意图分类器（BGE 语义相似度 + 关键词双重兜底）

识别策略（按优先级）：
1. 写操作强触发词（_WRITE_TRIGGERS）：取消订单/确认收货/申请退款/改地址等，
   命中即返回，不依赖语义相似度（保证写操作 100% 路由正确）
2. 高精度强触发词（_STRONG_TRIGGERS）：多少钱/质量太差/转人工等，
   避免语义模型把这些明显意图漂移到其他类别
3. BGE-large 语义相似度：用户问题向量与 12 类意图描述向量做余弦匹配，
   可捕获"东西到哪了 → track_logistics"这类语义变体
4. 关键词规则兜底（KEYWORD_RULES）：ML 不可用或低置信度（<0.5）时回退

设计取舍：
- 意图描述在初始化时一次性向量化（_precompute），运行时只算用户向量，
  单次分类耗时约 1-2s（CPU）；文件级 query 向量缓存进一步降低重复成本
- 置信度阈值 0.5：过低会误判，过高会漏判；低于阈值交给关键词兜底
"""
import time
from dataclasses import dataclass

import numpy as np
from loguru import logger

from app.knowledge.embedding import embed_query_cached, get_embeddings

perf_logger = logger.bind(name="perf")

# 12 类客服意图 + 自然语言描述（用于 embedding 语义匹配）
INTENT_DESCRIPTIONS: dict[str, str] = {
    "query_order": (
        "查询订单状态、订单详情、订单编号、我的订单在哪、发货情况、"
        "订单什么时候发货、有没有发货、订单情况如何"
    ),
    "track_logistics": (
        "物流追踪、快递查询、包裹到哪了、几天能到、物流进度、"
        "快递单号、物流信息、什么时候收到货、运输情况"
    ),
    "return_goods": (
        "退货申请、退款、不想要了、七天无理由退货、申请售后、"
        "退货流程、退款到账、怎么退货、如何退款"
    ),
    "exchange_goods": (
        "换货、换一件、换款、换尺寸、收到货不对、发错了"
    ),
    "product_consult": (
        "茶叶咨询、有什么茶叶、龙井碧螺春普洱铁观音大红袍、"
        "红茶绿茶白茶乌龙茶岩茶、冲泡方法、怎么泡、如何保存、"
        "送礼推荐、礼盒、茶具、茶叶品种介绍、品鉴"
    ),
    "price_inquiry": (
        "多少钱、价格、便宜吗、优惠吗、有没有折扣、包邮吗、"
        "价格查询、贵不贵、怎么收费"
    ),
    "promotion_consult": (
        "优惠券、满减、活动、折扣、会员、积分、促销、"
        "有什么优惠、打折、限时活动、新用户福利"
    ),
    "payment_issue": (
        "支付失败、扣款了但订单没成功、付款问题、无法支付、"
        "支付异常、发票、分期、支付方式"
    ),
    "app_usage": (
        "App闪退、登录不上、验证码收不到、页面打不开、"
        "怎么使用、功能在哪里、系统问题、报错"
    ),
    "complaint": (
        "投诉、差评、举报、315投诉、服务不好、质量问题、"
        "非常不满意、我要投诉、态度差"
    ),
    "human_service": (
        "人工客服、转人工、真人客服、人工服务、找人工、"
        "联系客服、人工帮助、不想要机器人"
    ),
    "chitchat": (
        "你好、谢谢、再见、闲聊、打招呼、天气、今天怎么样、"
        "你是谁、你叫什么、你是机器人吗"
    ),
}

# 保留关键词规则作为 embedding 不可用时的降级兜底
KEYWORD_RULES: dict[str, list[str]] = {
    "return_goods": ["退货", "退款", "不想要了", "七天无理由"],
    "exchange_goods": ["换货", "换一件", "换款"],
    "query_order": ["订单号", "查订单", "订单状态", "订单到哪", "什么时候发货", "发货了吗",
                     "待付款", "我的订单", "订单详情", "订单编号", "订单情况"],
    "track_logistics": ["物流", "快递", "到哪了", "包裹", "什么时候到", "几天到"],
    "promotion_consult": ["优惠券", "满减", "活动", "折扣", "会员", "积分"],
    "price_inquiry": ["多少钱", "价格", "便宜", "优惠", "包邮"],
    "payment_issue": ["支付失败", "扣款", "付款", "发票", "分期"],
    "app_usage": ["app", "闪退", "登录不上", "验证码"],
    "complaint": ["投诉", "差评", "举报", "315", "质量太差", "太差了", "非常不满意"],
    "human_service": ["人工", "转人工", "真人客服"],
    "chitchat": ["你好", "谢谢", "再见", "你是谁"],
}

# 写操作类强触发词：优先于语义分类，确保"取消/确认收货/改地址/申请退款"直达对应Agent
_WRITE_TRIGGERS: dict[str, list[str]] = {
    "query_order": ["取消订单", "确认收货", "改地址", "修改地址", "改收货地址", "换地址", "地址改"],
    "return_goods": ["申请退款", "帮我退款", "要退款"],
}

# 强触发词：高精度词直接命中意图，避免语义分类漂移
_STRONG_TRIGGERS: dict[str, list[str]] = {
    "price_inquiry": ["多少钱一斤", "多少钱", "什么价格", "价格多少"],
    "complaint": ["质量太差", "太差了", "非常不满意"],
    "human_service": ["转人工", "找人工", "真人客服"],
}


@dataclass
class IntentResult:
    name: str
    confidence: float


class IntentClassifier:
    """基于 Embedding 语义相似度的意图分类器

    使用已加载的 BGE-large-zh-v1.5 模型，对用户输入与各意图描述
    做余弦相似度匹配。首次实例化时会预计算所有意图描述的 embedding。
    """

    def __init__(self) -> None:
        """初始化：加载 embedding 模型并预计算全部意图描述向量"""
        self._embeddings = get_embeddings()
        self._intent_emb: dict[str, np.ndarray] = {}
        self._intents: list[str] = []
        self._emb_matrix: np.ndarray | None = None
        self._ml_ready = False
        self._precompute()

    def _precompute(self) -> None:
        """预计算所有意图描述的归一化 embedding 向量

        只在首次实例化时执行一次；后续 classify 只需计算用户查询向量，
        与 12 个意图向量做点积（归一化后点积=余弦相似度）。
        """
        try:
            self._intents = list(INTENT_DESCRIPTIONS.keys())
            vectors = []
            for intent in self._intents:
                vec = np.array(self._embeddings.embed_query(INTENT_DESCRIPTIONS[intent]))
                vectors.append(vec)
            self._emb_matrix = np.stack(vectors)  # shape: (12, 1024)
            # 确保已归一化（BGE 模型默认 normalize_embeddings=True）
            self._intent_emb = dict(zip(self._intents, vectors))
            self._ml_ready = True
        except Exception:
            self._ml_ready = False

    def classify(self, text: str, history: list | None = None) -> IntentResult:
        """对用户输入做意图分类（四层优先级，见模块 docstring）

        Args:
            text: 用户输入文本
            history: 对话历史（可选，暂用于未来上下文消歧）

        Returns:
            IntentResult: 意图名称与置信度(0~1)
        """
        if not text or not text.strip():
            return IntentResult(name="chitchat", confidence=0.5)

        # ① 写操作强触发词（保证取消/确认/退款/改址路由正确）
        for intent, kws in _WRITE_TRIGGERS.items():
            if any(k in text for k in kws):
                return IntentResult(name=intent, confidence=0.9)
        # ② 高精度强触发词（价格/投诉/转人工）
        for intent, kws in _STRONG_TRIGGERS.items():
            if any(k in text for k in kws):
                return IntentResult(name=intent, confidence=0.9)

        # ③ BGE 语义匹配（主流路径）
        if self._ml_ready and self._emb_matrix is not None:
            try:
                t0 = time.perf_counter()
                query_vec = embed_query_cached(text)
                t_embed = time.perf_counter() - t0
                # 余弦相似度（embedding 已归一化，点积即余弦）
                scores = np.dot(self._emb_matrix, query_vec)
                best_idx = int(np.argmax(scores))
                confidence = float(scores[best_idx])

                # 置信度阈值：低于 0.5 时回退关键词兜底
                if confidence >= 0.5:
                    perf_logger.debug(f"[intent] ML: {(time.perf_counter() - t0 + t_embed) * 1000:.0f}ms (embed={t_embed * 1000:.0f}ms), {self._intents[best_idx]}({confidence:.3f})")
                    return IntentResult(name=self._intents[best_idx], confidence=confidence)
                else:
                    perf_logger.debug(f"[intent] ML low_conf {confidence:.3f} -> fallback to keywords")
            except Exception:
                pass

        # ④ 降级：关键词规则兜底（ML 不可用或低置信度）
        t0 = time.perf_counter()
        result = self._classify_by_keywords(text)
        perf_logger.debug(f"[intent] keyword: {(time.perf_counter() - t0) * 1000:.0f}ms, {result.name}({result.confidence:.2f})")
        return result

    def _classify_by_keywords(self, text: str) -> IntentResult:
        """关键词规则兜底（ML 不可用或低置信度时）"""
        for intent, keywords in KEYWORD_RULES.items():
            if any(kw in text for kw in keywords):
                return IntentResult(name=intent, confidence=0.75)
        return IntentResult(name="product_consult", confidence=0.5)
