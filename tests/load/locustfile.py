"""Locust 压测脚本：商城浏览 + 客服对话（容量基线）

用法：
    locust -f tests/load/locustfile.py -H http://127.0.0.1:8000 --headless -u 100 -r 10 -t 5m
"""

from locust import HttpUser, between, task


class ShopUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health(self):
        self.client.get("/api/health")

    @task(1)
    def products(self):
        self.client.get("/api/products?page_size=12")

    @task(1)
    def openapi(self):
        """开放平台健康检查：避免无鉴权触发 401 污染基线"""
        self.client.get("/api/openapi/v1/health")
