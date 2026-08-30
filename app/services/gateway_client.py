"""电商业务API Gateway统一客户端：鉴权、超时、重试（TODO: 熔断）"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import settings


class GatewayClient:
    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=settings.biz_api_gateway_url,
                headers={"Authorization": f"Bearer {settings.biz_api_token}"},
                timeout=5.0,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.2, max=2), reraise=True)
    def get(self, path: str, params: dict | None = None) -> dict:
        resp = self.client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.2, max=2), reraise=True)
    def post(self, path: str, payload: dict | None = None) -> dict:
        resp = self.client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()

    # TODO: 熔断器（可引入 pybreaker），大促期间防止下游故障蔓延


gateway_client = GatewayClient()
