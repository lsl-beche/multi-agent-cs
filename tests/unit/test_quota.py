"""LLM 用户配额单元测试"""
from unittest.mock import patch

from app.config.settings import settings
from app.core.quota import allowed, consume


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expires = {}

    def get(self, key):
        return self.values.get(key)

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, ttl):
        self.expires[key] = ttl


def test_quota_blocks_after_limit():
    fake = FakeRedis()
    original = settings.llm_daily_quota
    settings.llm_daily_quota = 2
    try:
        with patch("app.core.redis_client.get_redis", return_value=fake):
            assert allowed("u1") == (True, 0, 2)
            assert consume("u1") is True
            assert consume("u1") is True
            assert consume("u1") is False
            assert allowed("u1") == (False, 3, 2)
    finally:
        settings.llm_daily_quota = original
