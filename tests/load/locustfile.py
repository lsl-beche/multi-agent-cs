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
    def chat(self):
        """客服对话（HTTP 兜底通道；无 token 会 401，此处以健康路径为主）"""
        self.client.post("/api/chat", json={
            "session_id": f"load-{self.environment.runner.user_count}",
            "user_id": "loadtest",
            "message": "龙井茶怎么泡",
        }, name="/api/chat")
