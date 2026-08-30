"""全局配置：通过 pydantic-settings 从 .env 读取"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ===== 环境 =====
    app_env: str = "development"  # development | staging | production

    # ===== LLM =====
    llm_provider: str = "local"  # local(本地GGUF,免Key) | deepseek | qwen 等云端
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_vllm_url: str = ""  # LLM_PROVIDER=vllm 时的推理集群地址
    llm_fast_model: str = ""  # 云端小模型（意图/摘要/偏好）
    llm_large_model: str = ""  # 云端大模型（复杂对话）
    # 自动降级：主 LLM 失败时切换的备用 OpenAI 兼容渠道（如云端 API）
    llm_fallback_url: str = ""
    llm_fallback_key: str = ""
    llm_fallback_model: str = ""
    llm_temperature: float = 0.3

    # ===== 本地LLM（llama.cpp，免API Key）=====
    local_llm_model_path: str = "./models/Qwen3-1.7B-Q8_0.gguf"
    local_llm_host: str = "127.0.0.1"
    local_llm_port: int = 8001
    local_llm_ctx: int = 1024

    # ===== Embedding / 向量库 =====
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rerank_model: str = ""  # CrossEncoder精排模型，留空禁用（如 "BAAI/bge-reranker-v2-m3"）
    vector_db_type: str = "chroma"  # chroma | milvus
    chroma_persist_dir: str = "./data/vectordb"
    knowledge_version: str = "latest"  # 知识版本（灰度）；latest=不过滤版本
    qa_sim_threshold: float = 0.93  # QA 语义缓存命中阈值（可按命中率调优 0.88~0.93）
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # ===== 记忆与隐私 =====
    user_memory_enabled: bool = True   # 用户偏好/向量记忆总开关（隐私授权）
    memory_ttl_days: int = 90          # 对话向量记忆保留天数

    # ===== Agent 并发 =====
    agent_max_concurrency: int = 4     # 客服工作流并发上限（保护LLM）

    # ===== 客服成本 =====
    llm_cost_per_1k_tokens: float = 0.001  # 单千token成本估算（元），用于成本看板

    # ===== 存储 =====
    postgres_url: str = "postgresql+psycopg://postgres:password@localhost:5432/csagent"
    # 分库分表：按 user_id 哈希路由；开发环境单库（1 个 shard）行为不变
    pg_shard_urls: list[str] = []  # 生产：[url0, url1, ...]，为空时退化为 postgres_url
    redis_url: str = "redis://localhost:6379/0"
    redis_cluster_nodes: list[str] = []  # 生产：[{"host":..,"port":..}, ...]，为空时用单机

    # ===== 事件总线 =====
    event_bus_backend: str = "memory"  # memory | kafka（生产切换）
    kafka_bootstrap_servers: str = "localhost:9092"

    # ===== 电商业务API Gateway =====
    biz_api_gateway_url: str = "http://localhost:9000"
    biz_api_token: str = ""

    # ===== 服务 =====
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    # 安全密钥：生产必须通过环境变量注入，缺失时启动校验会拒绝
    api_secret_key: str = ""
    field_encryption_key: str = ""  # PII字段加密密钥（32字节base64）

    # ===== JWT =====
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15     # 15分钟（生产建议短时令牌+刷新轮换）
    jwt_refresh_token_expire_days: int = 7         # 7天

    # ===== 支付（沙箱/真实渠道）=====
    payment_gateway_provider: str = "sandbox"  # sandbox | wechat | alipay（生产接入真实渠道）
    payment_gateway_secret: str = ""           # 网关签名密钥（生产必须配置）
    payment_expire_minutes: int = 30           # 待支付订单/支付单超时时间
    # 真实渠道资质（接入微信/支付宝时配置）
    wechat_pay_mch_id: str = ""                # 微信商户号
    wechat_pay_app_id: str = ""                # 微信 AppID
    wechat_pay_apiv3_key: str = ""             # APIv3 密钥
    alipay_app_id: str = ""                    # 支付宝应用ID
    alipay_private_key_path: str = ""          # 应用私钥路径
    alipay_public_key_path: str = ""           # 支付宝公钥路径

    # ===== 订单 =====
    order_timeout_minutes: int = 30            # 未支付订单自动关闭时间

    # ===== 限流 =====
    rate_limit_per_second: int = 60  # 单IP每秒请求上限（页面并发+脚本共用IP场景）
    login_rate_limit_per_minute: int = 10  # 登录接口单IP每分钟上限（防爆破）
    chat_rate_limit_per_minute: int = 60  # 聊天接口单用户每分钟上限
    # 每分钟粒度（Redis 滑动窗口 / 管理接口）
    rate_limit_default: int = 100
    rate_limit_login: int = 5
    rate_limit_order: int = 10

    # ===== 跨域（生产收敛为域名白名单）=====
    cors_origins: list[str] = [
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ]

    # ===== 物流 =====
    logistics_provider: str = "sandbox"  # sandbox | kuaidi100 | cainiao（生产接入）


settings = Settings()
