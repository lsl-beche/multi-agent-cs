from unittest.mock import patch

from app.core import security
from app.core.security import decrypt_text, encrypt_text, mask_id_card, mask_phone


def test_encrypt_decrypt_roundtrip():
    with patch.object(security, "_fernet", None), patch.object(
        security.settings, "field_encryption_key", "test-key"
    ):
        token = encrypt_text("13800138000")
        assert decrypt_text(token) == "13800138000"


def test_mask_phone_and_id_card():
    assert mask_phone("13800138000") == "138****8000"
    assert mask_id_card("110101199001011234") == "1101**********1234"
