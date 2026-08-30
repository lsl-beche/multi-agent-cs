"""支付网关抽象：Provider 注册表 + 沙箱/微信/支付宝骨架

目标：把"模拟支付"升级为真实的 发起→回调→幂等确认 闭环。

Provider 注册表：
- sandbox（默认）：本地模拟，可跑完整闭环（发起/验签/幂等/退款）
- wechat / alipay：真实渠道骨架——未配置商户资质时启动会给出明确错误，
  接入时只需补齐 SDK 调用与回调验签（签名函数已按 HMAC 风格预留）

统一接口（create_payment / confirm_payment）保证上层路由不变。
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime

from app.config.settings import settings


def _gateway_secret() -> str:
    return settings.payment_gateway_secret or "sandbox-dev-secret"


def sign_payload(payload: dict) -> str:
    """HMAC-SHA256 签名：按 key 排序拼接后签名（与真实渠道风格一致）"""
    canonical = "&".join(f"{k}={payload[k]}" for k in sorted(payload) if payload[k] is not None)
    return hmac.new(_gateway_secret().encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(payload), signature or "")


class SandboxPaymentGateway:
    """沙箱网关：模拟微信/支付宝的支付创建与回调确认"""

    provider = "sandbox"

    def create_payment(self, order) -> dict:
        """生成待支付单（pending），返回模拟扫码信息与签名"""
        payment_no = f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
        trade_no = f"SANDBOX{secrets.token_hex(8).upper()}"
        payload = {
            "payment_no": payment_no,
            "trade_no": trade_no,
            "amount": float(order.pay_amount),
            "timestamp": int(time.time()),
        }
        return {
            **payload,
            "status": "pending",
            "mock_qr": f"sandbox://pay?payment_no={payment_no}",
            "expire_seconds": settings.payment_expire_minutes * 60,
            "signature": sign_payload(payload),
        }

    def confirm_payment(self, payment, order) -> None:
        """沙箱回调确认：标记支付成功、订单已支付（幂等）"""
        if payment.status == "paid":
            return
        payment.status = "paid"
        payment.paid_at = datetime.utcnow()
        order.pay_status = "paid"
        order.paid_at = datetime.utcnow()
        if order.order_status == "pending":
            order.order_status = "confirmed"


class WechatPayProvider:
    """微信支付 Provider 骨架（生产接入：统一下单 + APIv3 回调验签）

    前置配置：WECHAT_PAY_MCH_ID / WECHAT_PAY_APP_ID / WECHAT_PAY_APIV3_KEY
    """

    provider = "wechat"

    def create_payment(self, order) -> dict:
        from app.config.settings import settings
        if not (settings.wechat_pay_mch_id and settings.wechat_pay_app_id and settings.wechat_pay_apiv3_key):
            raise RuntimeError("微信支付未配置商户资质（MCH_ID/APP_ID/APIV3_KEY）")
        # TODO(生产): 调用微信统一下单，返回 prepay 参数/二维码
        raise NotImplementedError("微信支付 SDK 接入待商务与开发排期")


class AlipayProvider:
    """支付宝 Provider 骨架（生产接入：预下单 + 异步通知验签）"""

    provider = "alipay"

    def create_payment(self, order) -> dict:
        from app.config.settings import settings
        if not (settings.alipay_app_id and settings.alipay_private_key_path):
            raise RuntimeError("支付宝未配置商户资质（APP_ID/私钥）")
        # TODO(生产): 调用支付宝预下单，返回收银台 URL
        raise NotImplementedError("支付宝 SDK 接入待商务与开发排期")


def get_gateway():
    """按配置返回支付网关 Provider（真实渠道未就绪时给出明确配置错误）"""
    if settings.payment_gateway_provider == "sandbox":
        return SandboxPaymentGateway()
    if settings.payment_gateway_provider == "wechat":
        return WechatPayProvider()
    if settings.payment_gateway_provider == "alipay":
        return AlipayProvider()
    raise ValueError(f"不支持的支付网关: {settings.payment_gateway_provider}")
