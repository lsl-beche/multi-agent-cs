# 环境规范

## 总则

- `.env` 不进入 Git；
- 所有变量先在 `.env.example` 中声明；
- 生产环境密钥通过 KMS / Secret Manager 或 CI Secret 注入，不写入代码；
- 环境值按 `development / staging / production` 分离；
- 生产环境启动前必须通过 `app/config/validate.py` 校验。

## 必填变量

| 变量 | 示例 | 说明 |
|---|---|---|
| `APP_ENV` | `development` | development / staging / production |
| `POSTGRES_URL` | `postgresql+psycopg://postgres:****@host:5432/csagent` | 生产使用内网、强密码 |
| `REDIS_URL` | `redis://host:6379/0` | 生产使用 Tair 内网 |
| `API_SECRET_KEY` | 随机 64 位 hex | Fernet 派生密钥 |
| `JWT_SECRET_KEY` | 随机 64 位 hex | 至少 32 字符 |
| `FIELD_ENCRYPTION_KEY` | Fernet 生成的 base64 | PII 字段加密 |
| `APP_HOST` | `0.0.0.0` | 容器内绑定地址 |
| `APP_PORT` | `8000` | 服务端口 |

## LLM / AI

| 变量 | 说明 |
|---|---|
| `LLM_PROVIDER` | `local` / `deepseek` / `qwen` / `vllm` |
| `LLM_API_KEY` | 云端模型密钥，本地模式可空 |
| `LLM_BASE_URL` | OpenAI 兼容地址 |
| `LLM_MODEL` | 主模型 |
| `LLM_FAST_MODEL` | 意图/摘要/偏好等小模型 |
| `LLM_FALLBACK_URL` | 主模型故障时降级地址 |
| `EMBEDDING_MODEL` | BGE 中文向量模型 |
| `VECTOR_DB_TYPE` | chroma / pgvector |

## 支付与物流

| 变量 | 说明 |
|---|---|
| `PAYMENT_GATEWAY_PROVIDER` | sandbox / wechat / alipay |
| `PAYMENT_GATEWAY_SECRET` | 真实渠道必须配置 |
| `WECHAT_PAY_MCH_ID` | 微信商户号（可选） |
| `WECHAT_PAY_APIV3_KEY` | 微信 APIv3 密钥 |
| `ALIPAY_APP_ID` | 支付宝应用 ID |
| `ALIPAY_PRIVATE_KEY_PATH` | 应用私钥路径 |
| `LOGISTICS_PROVIDER` | sandbox / kuaidi100 / cainiao |

## 限流与 CORS

| 变量 | 说明 |
|---|---|
| `RATE_LIMIT_DEFAULT` | 普通接口每分钟限制 |
| `RATE_LIMIT_LOGIN` | 登录/注册每分钟限制 |
| `RATE_LIMIT_ORDER` | 下单每分钟限制 |
| `CORS_ORIGINS` | JSON 数组，生产为明确域名白名单 |

## 密钥生成

```bash
# API / JWT 密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 字段加密密钥
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 禁止提交

```text
.env
.env.production
*.pem
*.key
*.p12
```

## 生产启动校验

生产环境缺失以下任一配置时必须拒绝启动：

- `JWT_SECRET_KEY` 缺失、过短或为默认值；
- `API_SECRET_KEY` 缺失或为默认值；
- `FIELD_ENCRYPTION_KEY` 缺失；
- PostgreSQL 弱口令；
- CORS 使用 `*`。

