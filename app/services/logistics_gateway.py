"""物流网关抽象：Provider 注册表（沙箱 + 真实渠道骨架）

- sandbox（默认）：按发货时间模拟轨迹（揽收/运输/派送/签收）
- kuaidi100 / cainiao：真实渠道骨架——需第三方 API Key，
  接入后由轮询/Webhook 更新轨迹，替换沙箱模拟
"""
import logging
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


class SandboxLogisticsProvider:
    """沙箱物流：按发货后经过的小时数推进轨迹"""

    provider = "sandbox"

    def track(self, tracking_no: str, shipped_at: datetime | None, carrier: str = "") -> dict:
        if not shipped_at:
            return {"tracking_no": tracking_no, "status": "pending", "events": []}
        hours = (datetime.utcnow() - shipped_at).total_seconds() / 3600
        events = [{"time": shipped_at.strftime("%m-%d %H:%M"), "desc": f"{carrier} 已揽收"}]
        if hours >= 2:
            events.append({"time": (shipped_at + timedelta(hours=2)).strftime("%m-%d %H:%M"), "desc": "快件到达转运中心，运输中"})
        if hours >= 24:
            events.append({"time": (shipped_at + timedelta(hours=24)).strftime("%m-%d %H:%M"), "desc": "快件到达目的城市，派送中"})
        if hours >= 72:
            events.append({"time": (shipped_at + timedelta(hours=72)).strftime("%m-%d %H:%M"), "desc": "已签收，感谢使用"})
        status = "delivered" if hours >= 72 else ("shipped" if hours >= 2 else "pending")
        return {"tracking_no": tracking_no, "status": status, "events": events}


class Kuaidi100Provider:
    provider = "kuaidi100"

    def track(self, tracking_no: str, shipped_at: datetime | None, carrier: str = "") -> dict:
        from app.config.settings import settings
        if not settings.logistics_api_url or not settings.logistics_api_key:
            raise RuntimeError("快递100未配置 LOGISTICS_API_URL/LOGISTICS_API_KEY")
        resp = httpx.get(
            f"{settings.logistics_api_url.rstrip('/')}/track",
            params={"tracking_no": tracking_no, "carrier": carrier},
            headers={"Authorization": f"Bearer {settings.logistics_api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


class CainiaoProvider:
    provider = "cainiao"

    def track(self, tracking_no: str, shipped_at: datetime | None, carrier: str = "") -> dict:
        from app.config.settings import settings
        if not settings.logistics_api_url or not settings.logistics_api_key:
            raise RuntimeError("菜鸟物流未配置 LOGISTICS_API_URL/LOGISTICS_API_KEY")
        resp = httpx.get(
            f"{settings.logistics_api_url.rstrip('/')}/track",
            params={"tracking_no": tracking_no, "carrier": carrier},
            headers={"Authorization": f"Bearer {settings.logistics_api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


def get_logistics_provider():
    from app.config.settings import settings
    if settings.logistics_provider == "sandbox":
        return SandboxLogisticsProvider()
    if settings.logistics_provider == "kuaidi100":
        return Kuaidi100Provider()
    if settings.logistics_provider == "cainiao":
        return CainiaoProvider()
    raise NotImplementedError(f"不支持的物流渠道: {settings.logistics_provider}")
