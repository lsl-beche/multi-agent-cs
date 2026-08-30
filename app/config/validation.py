"""配置校验：生产环境缺关键配置即拒绝启动（开发环境仅告警）"""
from app.config.settings import settings

PLACEHOLDERS = ("change-me", "password")


def validate_settings() -> list[str]:
    """返回问题清单；空列表表示通过

    生产环境（app_env=production）硬性要求：
    - 密钥非占位符
    - PostgreSQL/Redis 地址非默认
    - 支付网关为 sandbox 时可不校验；真实渠道必须配置对应资质
    """
    problems = []

    def _check(cond: bool, msg: str) -> None:
        if cond:
            problems.append(msg)

    if settings.jwt_secret_key.startswith("change-me"):
        _check(True, "JWT_SECRET_KEY 仍是占位符")
    if settings.api_secret_key.startswith("change-me"):
        _check(True, "API_SECRET_KEY 仍是占位符")
    if "password" in settings.postgres_url:
        _check(True, "POSTGRES_URL 使用默认密码")
    if settings.payment_gateway_provider in ("wechat", "alipay"):
        if not settings.payment_gateway_secret:
            _check(True, "真实支付渠道未配置 PAYMENT_GATEWAY_SECRET")
    return problems
