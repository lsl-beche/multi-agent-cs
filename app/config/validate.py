"""启动配置校验：生产环境缺失关键密钥时拒绝启动"""
from loguru import logger
from sqlalchemy.engine.url import make_url

from app.config.settings import settings

FORBIDDEN_DEFAULTS = {"change-me-in-production", "change-me-in-production-jwt-secret-key-at-least-32-chars"}


def validate_security_config() -> None:
    """校验安全配置完整性。生产环境不通过则终止；开发环境仅警告。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not settings.jwt_secret_key:
        errors.append("JWT_SECRET_KEY 未配置")
    elif settings.jwt_secret_key in FORBIDDEN_DEFAULTS:
        errors.append("JWT_SECRET_KEY 使用了已知默认值，必须更换")
    elif len(settings.jwt_secret_key) < 32:
        errors.append("JWT_SECRET_KEY 长度不足32字符")

    if not settings.api_secret_key:
        errors.append("API_SECRET_KEY 未配置")
    elif settings.api_secret_key in FORBIDDEN_DEFAULTS:
        errors.append("API_SECRET_KEY 使用了已知默认值，必须更换")

    if settings.app_env == "production":
        if not settings.field_encryption_key:
            errors.append("生产环境必须配置 FIELD_ENCRYPTION_KEY（32字节base64）")

        db_password = make_url(settings.postgres_url).password or ""
        if db_password in ("password", "123456", ""):
            errors.append("生产环境 PostgreSQL 密码不能是弱口令")

        if not settings.cors_origins or "*" in settings.cors_origins:
            errors.append("生产环境 CORS 不允许使用通配符")
    else:
        # 开发环境仅提示
        if not settings.jwt_secret_key:
            warnings.append("JWT_SECRET_KEY 未配置，开发环境请配置随机密钥")
        if not settings.field_encryption_key:
            warnings.append("FIELD_ENCRYPTION_KEY 未配置")

    if errors:
        logger.critical("安全配置校验失败，拒绝启动：")
        for e in errors:
            logger.critical(f"  - {e}")
        logger.info("请通过环境变量或 .env 文件配置以上密钥")
        raise RuntimeError("安全配置校验失败：" + "; ".join(errors))

    if warnings:
        for w in warnings:
            logger.warning(f"安全提示: {w}")
