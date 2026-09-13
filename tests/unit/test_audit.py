"""审计写入单元测试"""
from unittest.mock import patch

from app.core.audit import record_audit, sanitize


class FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_audit_writes_operation_log():
    fake = FakeDb()
    with patch("app.core.audit.SessionLocal", return_value=fake):
        record_audit(
            user_id=1, username="admin", module="system", action="test",
            target_id="1", detail={"phone": "13812345678", "email": "a@example.com"},
        )
    assert fake.committed is True
    assert len(fake.added) == 1


def test_sanitize_masks_pii():
    result = sanitize("手机 13812345678 邮箱 alice@example.com")
    assert "***" in result
    assert "alice" not in result
