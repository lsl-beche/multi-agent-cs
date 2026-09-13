"""支付网关：Provider 注册表（沙箱 / 微信 APIv3 / 支付宝 RSA2）

统一接口：create_payment / confirm_payment（沙箱）/ refund / query_order /
verify_callback，上层路由（shop_payments）只依赖这些约定。

- sandbox（默认）：本地闭环，供开发/CI/1000 笔对账刷量
- wechat：微信支付 APIv3（Native 下单、请求签名、回调验签+解密、退款）
- alipay：支付宝（电脑网站支付、RSA2 签名/验签、退款）

生产接入：配置商户资质后切换 provider 即可；未配置时调用给出明确错误。
"""
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime

import httpx

from app.config.settings import settings


def _gateway_secret() -> str:
    return settings.payment_gateway_secret or "sandbox-dev-secret"


def _notify_url() -> str:
    """兼容新旧配置项：PAYMENT_GATEWAY_NOTIFY_URL 优先。"""
    return settings.payment_gateway_notify_url or settings.payment_notify_url


def sign_payload(payload: dict) -> str:
    """HMAC-SHA256 签名（沙箱契约）：按 key 排序拼接后签名"""
    canonical = "&".join(f"{k}={payload[k]}" for k in sorted(payload) if payload[k] is not None)
    return hmac.new(_gateway_secret().encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(payload), signature or "")


class SandboxPaymentGateway:
    """沙箱网关：模拟微信/支付宝的支付创建与回调确认（本地闭环）"""

    provider = "sandbox"

    def create_payment(self, order) -> dict:
        payment_no = f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
        trade_no = f"SANDBOX{secrets.token_hex(8).upper()}"
        payload = {"payment_no": payment_no, "trade_no": trade_no,
                   "amount": float(order.pay_amount), "timestamp": int(time.time())}
        return {**payload, "status": "pending",
                "mock_qr": f"sandbox://pay?payment_no={payment_no}",
                "expire_seconds": settings.payment_expire_minutes * 60,
                "signature": sign_payload(payload)}

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

    def query_order(self, out_trade_no: str) -> dict:
        return {"out_trade_no": out_trade_no, "trade_state": "SUCCESS", "channel": "sandbox"}

    def refund(self, out_trade_no: str, refund_no: str, amount: float, reason: str = "",
               total: float | None = None) -> dict:
        return {"out_trade_no": out_trade_no, "out_refund_no": refund_no, "status": "SUCCESS"}


class WechatPayProvider:
    """微信支付 Provider（APIv3 Native）——生产实现，可直连渠道

    配置：WECHAT_PAY_MCH_ID / APP_ID / APIV3_KEY / PRIVATE_KEY_PATH / NOTIFY_URL
    安全：请求签名 SHA256-RSA2048；回调验签（平台证书）+ AES-256-GCM 解密。
    """

    provider = "wechat"
    BASE = "https://api.mch.weixin.qq.com"

    def create_payment(self, order) -> dict:
        if not (settings.wechat_pay_mch_id and settings.wechat_pay_app_id and settings.wechat_pay_apiv3_key):
            raise RuntimeError("微信支付未配置商户资质（MCH_ID/APP_ID/APIV3_KEY）")
        payload = {
            "appid": settings.wechat_pay_app_id,
            "mchid": settings.wechat_pay_mch_id,
            "description": f"茗韵茶庄订单 {order.order_no}",
            "out_trade_no": order.order_no,
            "notify_url": _notify_url(),
            "amount": {"total": int(round(order.pay_amount * 100)), "currency": "CNY"},
        }
        resp = self._request("POST", "/v3/pay/transactions/native", payload)
        return {"payment_no": order.order_no, "code_url": resp.get("code_url", ""),
                "status": "pending", "expire_seconds": settings.payment_expire_minutes * 60}

    def verify_callback(self, headers: dict, body: bytes) -> dict:
        """APIv3 回调：平台证书验签 + AES-256-GCM 解密，返回支付结果"""
        from app.core.security import wechat_decrypt_resource, wechat_verify_signature
        if not wechat_verify_signature(headers, body):
            raise ValueError("微信回调验签失败")
        payload = wechat_decrypt_resource(body, settings.wechat_pay_apiv3_key)
        return {"out_trade_no": payload.get("out_trade_no", ""),
                "trade_no": payload.get("transaction_id", ""),
                "trade_state": payload.get("trade_state", ""),
                "amount": payload.get("amount", {}).get("total", 0) / 100}

    def verify_refund_callback(self, headers: dict, body: bytes) -> dict:
        """APIv3 退款回调：验签并解密 REFUND.* 资源"""
        from app.core.security import wechat_decrypt_resource, wechat_verify_signature
        if not wechat_verify_signature(headers, body):
            raise ValueError("微信退款回调验签失败")
        payload = wechat_decrypt_resource(body, settings.wechat_pay_apiv3_key)
        return {
            "out_refund_no": payload.get("out_refund_no", ""),
            "out_trade_no": payload.get("out_trade_no", ""),
            "refund_status": payload.get("refund_status", ""),
            "amount": payload.get("amount", {}).get("refund", 0) / 100,
            "trade_no": payload.get("transaction_id", ""),
        }

    def query_order(self, out_trade_no: str) -> dict:
        resp = self._request("GET", f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={settings.wechat_pay_mch_id}")
        return {"out_trade_no": out_trade_no, "trade_state": resp.get("trade_state", ""),
                "trade_no": resp.get("transaction_id", "")}

    def close_order(self, out_trade_no: str) -> dict:
        return self._request("POST", f"/v3/pay/transactions/out-trade-no/{out_trade_no}/close",
                             {"mchid": settings.wechat_pay_mch_id})

    def refund(self, out_trade_no: str, refund_no: str, amount: float, reason: str = "",
               total: float | None = None) -> dict:
        total_amount = total if total is not None else amount
        return self._request("POST", "/v3/refund/domestic/refunds", {
            "out_trade_no": out_trade_no, "out_refund_no": refund_no, "reason": reason[:80],
            "amount": {"refund": int(round(amount * 100)), "total": int(round(total_amount * 100)), "currency": "CNY"},
        })

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        from app.core.security import wechat_build_authorization
        body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
        auth = wechat_build_authorization(method, path, body)
        resp = httpx.request(method, self.BASE + path, content=body or None,
                             headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=10)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


class AlipayProvider:
    """支付宝 Provider（电脑网站支付）——生产实现，可直连渠道"""

    provider = "alipay"
    BASE = "https://openapi.alipay.com/gateway.do"

    def create_payment(self, order) -> dict:
        if not (settings.alipay_app_id and settings.alipay_private_key_path):
            raise RuntimeError("支付宝未配置商户资质（APP_ID/私钥）")
        params = {
            "app_id": settings.alipay_app_id, "method": "alipay.trade.page.pay",
            "charset": "utf-8", "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0",
            "notify_url": _notify_url(),
            "biz_content": json.dumps({
                "out_trade_no": order.order_no, "total_amount": f"{order.pay_amount:.2f}",
                "subject": f"茗韵茶庄订单 {order.order_no}", "product_code": "FAST_INSTANT_TRADE_PAY",
            }, ensure_ascii=False),
        }
        from app.core.security import alipay_sign
        params["sign"] = alipay_sign(params)
        from urllib.parse import urlencode
        return {"payment_no": order.order_no, "pay_url": f"{self.BASE}?{urlencode(params)}", "status": "pending"}

    def verify_callback(self, form: dict) -> dict:
        from app.core.security import alipay_verify
        if not alipay_verify(form):
            raise ValueError("支付宝回调验签失败")
        return {"out_trade_no": form.get("out_trade_no", ""), "trade_no": form.get("trade_no", ""),
                "trade_state": form.get("trade_status", ""),
                "amount": float(form.get("total_amount", 0) or 0)}

    def verify_refund_callback(self, form: dict) -> dict:
        """支付宝异步退款通知验签"""
        from app.core.security import alipay_verify
        if not alipay_verify(form):
            raise ValueError("支付宝退款回调验签失败")
        return {
            "out_refund_no": form.get("out_biz_no") or form.get("out_request_no") or "",
            "out_trade_no": form.get("out_trade_no", ""),
            "refund_status": form.get("refund_status") or form.get("status") or form.get("trade_status", ""),
            "amount": float(form.get("refund_fee", 0) or 0),
            "trade_no": form.get("trade_no", ""),
        }

    def query_order(self, out_trade_no: str) -> dict:
        return self._rpc("alipay.trade.query", {"out_trade_no": out_trade_no})

    def refund(self, out_trade_no: str, refund_no: str, amount: float, reason: str = "",
               total: float | None = None) -> dict:
        return self._rpc("alipay.trade.refund", {
            "out_trade_no": out_trade_no, "refund_amount": f"{amount:.2f}",
            "out_request_no": refund_no, "refund_reason": reason[:80]})

    def _rpc(self, method: str, biz: dict) -> dict:
        from datetime import datetime as _dt

        import httpx

        from app.core.security import alipay_sign
        params = {"app_id": settings.alipay_app_id, "method": method, "format": "JSON",
                  "charset": "utf-8", "sign_type": "RSA2",
                  "timestamp": _dt.now().strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0",
                  "biz_content": json.dumps(biz, ensure_ascii=False)}
        params["sign"] = alipay_sign(params)
        resp = httpx.post(self.BASE, data=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get(method.rsplit(".", 1)[-1] + "_response", data)


def get_gateway():
    """按配置返回支付网关 Provider（未配置资质的真实渠道会在调用时报明确错误）"""
    if settings.payment_gateway_provider == "sandbox":
        return SandboxPaymentGateway()
    if settings.payment_gateway_provider == "wechat":
        return WechatPayProvider()
    if settings.payment_gateway_provider == "alipay":
        return AlipayProvider()
    raise ValueError(f"不支持的支付网关: {settings.payment_gateway_provider}")
