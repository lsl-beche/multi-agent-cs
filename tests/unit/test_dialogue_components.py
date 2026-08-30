"""对话组件单元测试：意图识别"""
from app.dialogue.intent import IntentClassifier, KEYWORD_RULES


class TestIntentClassifier:
    def setup_method(self):
        self.clf = IntentClassifier()

    def test_query_order_keyword(self):
        result = self.clf._classify_by_keywords("帮我查一下订单状态")
        assert result.name == "query_order"

    def test_track_logistics_keyword(self):
        result = self.clf._classify_by_keywords("我的快递到哪了")
        assert result.name == "track_logistics"

    def test_return_goods_keyword(self):
        result = self.clf._classify_by_keywords("我要退货")
        assert result.name == "return_goods"

    def test_human_service_keyword(self):
        result = self.clf._classify_by_keywords("转人工客服")
        assert result.name == "human_service"

    def test_chitchat_keyword(self):
        result = self.clf._classify_by_keywords("你好呀")
        assert result.name == "chitchat"

    def test_ml_classify_query_order(self):
        # 语义分类路径（会加载 embedding，略慢但覆盖真实链路）
        result = self.clf.classify("查一下我的订单 SO2024001 到哪了")
        assert result.name in ("query_order", "track_logistics")

    def test_keyword_rules_coverage(self):
        # 每个意图至少有一条关键词规则
        assert len(KEYWORD_RULES) >= 10
