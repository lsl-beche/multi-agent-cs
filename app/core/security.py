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

# ── 微信支付 APIv3 安全工具（请求签名 / 回调验签 / 回调解密）──

def _load_pem(path: str) -> bytes:
    from pathlib import Path
    return Path(path).read_bytes()


def wechat_build_authorization(method: str, path: str, body: str) -> str:
    """构造 APIv3 请求头 Authorization（SHA256-RSA2048 商户签名）"""
    import base64
    import uuid

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(__import__("time").time()))
    nonce = uuid.uuid4().hex
    message = f"{method}\n{path}\n{ts}\n{nonce}\n{body}\n"
    private_key = serialization.load_pem_private_key(_load_pem(settings.wechat_pay_private_key_path), password=None)
    signature = base64.b64encode(private_key.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
    serial_no = settings.wechat_pay_cert_serial or settings.wechat_pay_mch_id
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{settings.wechat_pay_mch_id}",'
        f'nonce_str="{nonce}",signature="{signature}",timestamp="{ts}",serial_no="{serial_no}"'
    )


def wechat_verify_signature(headers: dict, body: bytes) -> bool:
    """回调验签：用平台证书验证 Wechatpay-Signature（生产必需）"""
    import base64

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        header_map = {str(k).lower(): v for k, v in headers.items()}
        signature = header_map.get("wechatpay-signature", "")
        timestamp = header_map.get("wechatpay-timestamp", "")
        nonce = header_map.get("wechatpay-nonce", "")
        message = f"{timestamp}\n{nonce}\n{body.decode()}\n"
        cert = serialization.load_pem_x509_certificate(_load_pem(settings.wechat_pay_platform_cert_path))
        cert.public_key().verify(base64.b64decode(signature), message.encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def wechat_decrypt_resource(body: bytes, apiv3_key: str) -> dict:
    """回调 resource 解密：AES-256-GCM（APIv3 密钥）"""
    import json

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    data = json.loads(body)
    resource = data.get("resource", {})
    ciphertext = __import__("base64").b64decode(resource.get("ciphertext", ""))
    associated = resource.get("associated_data", "").encode()
    nonce = resource.get("nonce", "").encode()
    plain = AESGCM(apiv3_key.encode().ljust(32, b"0")[:32]).decrypt(nonce, ciphertext, associated)
    result = json.loads(plain)
    result["event_type"] = data.get("event_type", "")
    return result


# ── 支付宝 安全工具（RSA2 请求签名 / 回调验签）──

def _alipay_private_key():
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_private_key(_load_pem(settings.alipay_private_key_path), password=None)


def _alipay_public_key():
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_public_key(_load_pem(settings.alipay_public_key_path))


def alipay_sign(params: dict) -> str:
    """支付宝请求签名：剔除 sign/sign_type 后按键排序拼接，RSA2 签名"""
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    items = sorted((k, v) for k, v in params.items() if k not in ("sign", "sign_type") and v is not None)
    content = "&".join(f"{k}={v}" for k, v in items)
    sig = _alipay_private_key().sign(content.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def alipay_verify(form: dict) -> bool:
    """支付宝异步通知验签：用支付宝公钥验证 RSA2 签名"""
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        sign = form.pop("sign", "")
        form.pop("sign_type", None)
        content = "&".join(f"{k}={v}" for k, v in sorted(form.items()) if v is not None)
        _alipay_public_key().verify(base64.b64decode(sign), content.encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False

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
