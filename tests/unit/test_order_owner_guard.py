"""订单归属越权防护单测:登录用户只能操作自己的订单,游客放行(历史行为)。"""
from types import SimpleNamespace

from app.tools.order_tools import _owner_ok


def _order(user_id):
    return SimpleNamespace(user_id=user_id, order_status="pending")


def test_owner_match_allowed():
    assert _owner_ok(_order("u1"), "u1") is True


def test_owner_mismatch_denied():
    assert _owner_ok(_order("u1"), "u2") is False


def test_numeric_string_equivalence():
    """DB 里 user_id 是数字,入参可能是字符串:按字符串比较需一致。"""
    assert _owner_ok(_order("123"), "123") is True
    assert _owner_ok(_order("123"), "124") is False


def test_guest_without_user_id_allowed():
    """游客(无登录态)历史行为放行:订单号本身即凭证。"""
    assert _owner_ok(_order("u1"), "") is True
    assert _owner_ok(_order("u1"), "guest_abc") is True


def test_null_order_denied():
    assert _owner_ok(None, "u1") is False
