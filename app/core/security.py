"""数据安全：加密/脱敏 + JWT令牌 + 密码哈希"""
import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.config.settings import settings

_fernet: Fernet | None = None
_legacy_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key_source = settings.field_encryption_key or settings.api_secret_key
        if not key_source:
            raise RuntimeError("未配置 FIELD_ENCRYPTION_KEY / API_SECRET_KEY")
        if len(key_source) == 44:
            _fernet = Fernet(key_source.encode())
        else:
            derived = base64.urlsafe_b64encode(hashlib.sha256(key_source.encode()).digest())
            _fernet = Fernet(derived)
    return _fernet


def _get_legacy_fernet() -> Fernet:
    """兼容旧版 API_SECRET_KEY 加密数据"""
    global _legacy_fernet
    if _legacy_fernet is None:
        derived = base64.urlsafe_b64encode(hashlib.sha256(settings.api_secret_key.encode()).digest())
        _legacy_fernet = Fernet(derived)
    return _legacy_fernet


# ── 加密/脱敏 ────────────────────────────────────────


def encrypt_text(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_text(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        if settings.api_secret_key and settings.field_encryption_key:
            return _get_legacy_fernet().decrypt(token.encode()).decode()
        raise


def mask_phone(text: str) -> str:
    return re.sub(r"(1\d{2})\d{4}(\d{4})", r"\1****\2", text)


def mask_id_card(text: str) -> str:
    return re.sub(r"(\d{4})\d{10}(\d{4})", r"\1**********\2", text)


def mask_sensitive(text: str) -> str:
    return mask_id_card(mask_phone(text))


# ── 密码哈希 ─────────────────────────────────────────


def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT令牌 ─────────────────────────────────────────


def create_access_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    expire_min = expires_minutes or settings.jwt_access_token_expire_minutes
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_min),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    })
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any], expires_days: int | None = None) -> str:
    expire_days = expires_days or settings.jwt_refresh_token_expire_days
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.now(timezone.utc) + timedelta(days=expire_days),
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    })
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
