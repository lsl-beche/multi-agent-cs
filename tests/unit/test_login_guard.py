from unittest.mock import MagicMock, patch

from app.core.login_guard import check_login_allowed, record_login_failure


def test_login_guard_allows_when_redis_unavailable():
    with patch("app.core.login_guard._get_redis", side_effect=RuntimeError):
        allowed, reason = check_login_allowed("u", "1.2.3.4")
        assert allowed is True
        assert reason == ""


def test_login_guard_records_failure():
    redis = MagicMock()
    redis.incr.return_value = 1
    with patch("app.core.login_guard._get_redis", return_value=redis):
        record_login_failure("u", "1.2.3.4")
    assert redis.incr.called
