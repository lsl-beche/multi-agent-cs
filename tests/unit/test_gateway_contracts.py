from unittest.mock import MagicMock, patch

import pytest

from app.services.logistics_gateway import get_logistics_provider
from app.services.payment_gateway import WechatPayProvider


class FakeOrder:
    order_no = "ORDER-TEST-001"
    pay_amount = 99.0


def test_payment_gateway_requires_real_url():
    with patch("app.config.settings.settings.payment_gateway_url", ""):
        provider = WechatPayProvider()
        with pytest.raises(RuntimeError):
            provider.create_payment(FakeOrder())


def test_payment_gateway_calls_provider_url():
    from app.config.settings import settings

    response = MagicMock()
    response.json.return_value = {
        "code_url": "weixin://wxpay/bizpayurl?pr=test",
        "trade_no": "WXT-001",
        "amount": 99.0,
        "signature": "sig",
    }
    with (
        patch.object(settings, "wechat_pay_mch_id", "mch"),
        patch.object(settings, "wechat_pay_app_id", "app"),
        patch.object(settings, "wechat_pay_apiv3_key", "key"),
        patch("app.config.settings.settings.payment_gateway_url", "http://pay.local"),
        patch("app.core.security.wechat_build_authorization", return_value="fake-auth"),
        patch("app.services.payment_gateway.httpx.request", return_value=response) as mock_request,
    ):
        result = WechatPayProvider().create_payment(FakeOrder())
    assert result["payment_no"] == FakeOrder.order_no
    assert result["code_url"] == "weixin://wxpay/bizpayurl?pr=test"
    assert mock_request.call_args[0][1].endswith("/v3/pay/transactions/native")


def test_logistics_provider_requires_api_key():
    with patch("app.config.settings.settings.logistics_provider", "kuaidi100"):
        from app.services.logistics_gateway import Kuaidi100Provider

        with patch("app.config.settings.settings.logistics_api_url", ""), pytest.raises(RuntimeError):
            Kuaidi100Provider().track("123", None)


def test_logistics_provider_getter_sandbox():
    with patch("app.config.settings.settings.logistics_provider", "sandbox"):
        assert get_logistics_provider().provider == "sandbox"
