SET NAMES utf8mb4;

-- ============================================================
-- CSagent 订单服务(Java)表结构 v0.1
-- 从 CSagent app/models/tables.py 平移,MySQL 8 / InnoDB / utf8mb4
-- 由 Compose 挂载到 /docker-entrypoint-initdb.d 首次启动执行
-- ============================================================

-- 1. 商品 SPU(平移自 products,省略 subtitle/description/图片等展示字段)
CREATE TABLE IF NOT EXISTS products (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    spu_code    VARCHAR(64)  NOT NULL COMMENT 'SPU 编码',
    name        VARCHAR(256) NOT NULL,
    brand       VARCHAR(64)  NULL,
    status      VARCHAR(16)  NOT NULL DEFAULT 'draft' COMMENT 'draft/online/offline',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_spu_code (spu_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '商品 SPU';

-- 2. SKU
-- 设计决策:CSagent 把库存独立为 inventory 表(多仓 + version 乐观锁),
-- 本服务为单仓演示场景,将 stock/version 合并进 skus,减少一次联表;
-- 扣减语义不变:UPDATE ... WHERE stock >= n 原子防超卖。
CREATE TABLE IF NOT EXISTS skus (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    sku_code    VARCHAR(64)   NOT NULL COMMENT 'SKU 编码',
    product_id  BIGINT        NOT NULL,
    spec_info   JSON          NULL COMMENT '规格 JSON',
    price       DECIMAL(10,2) NOT NULL,
    stock       INT           NOT NULL DEFAULT 0 COMMENT '可售库存',
    version     INT           NOT NULL DEFAULT 1 COMMENT '乐观锁版本(CSagent 同名字段平移)',
    status      VARCHAR(16)   NOT NULL DEFAULT 'active',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sku_code (sku_code),
    KEY idx_product (product_id),
    CONSTRAINT fk_sku_product FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'SKU(含单仓库存)';

-- 3. 订单(平移自 orders 的查询/取消链路所需字段)
CREATE TABLE IF NOT EXISTS orders (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    order_no        VARCHAR(32)   NOT NULL COMMENT '业务订单号',
    user_id         BIGINT        NOT NULL,
    total_amount    DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    pay_amount      DECIMAL(10,2) NOT NULL,
    pay_status      VARCHAR(16)   NOT NULL DEFAULT 'unpaid' COMMENT 'unpaid/paid/refunded',
    order_status    VARCHAR(16)   NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/shipped/completed/cancelled',
    buyer_remark    VARCHAR(256)  NULL,
    version         INT           NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    paid_at         DATETIME      NULL,
    cancelled_at    DATETIME      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_user (user_id),
    KEY idx_pay_status (pay_status),
    KEY idx_order_status (order_status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '订单主表';

-- 3.5 订单商品行(创建订单时快照)
CREATE TABLE IF NOT EXISTS order_items (
    id           BIGINT        NOT NULL AUTO_INCREMENT,
    order_id     BIGINT        NOT NULL,
    sku_id       BIGINT        NOT NULL,
    product_name VARCHAR(256)  NOT NULL,
    unit_price   DECIMAL(10,2) NOT NULL,
    quantity     INT           NOT NULL,
    total_price  DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_order (order_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '订单商品行';

-- 4. 待确认提案(新增,本次方案核心)
-- 对应 Python 侧 Redis action_store 的 DB 化:原子状态迁移 + 惰性过期
CREATE TABLE IF NOT EXISTS pending_actions (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    session_id   VARCHAR(64)  NOT NULL COMMENT '客服会话 ID',
    user_id      BIGINT       NOT NULL,
    action_type  VARCHAR(32)  NOT NULL COMMENT 'CANCEL_ORDER/CONFIRM_RECEIPT/UPDATE_ADDRESS',
    order_id     BIGINT       NOT NULL,
    payload      JSON         NULL COMMENT '提案参数快照',
    status       VARCHAR(16)  NOT NULL DEFAULT 'PENDING'
                 COMMENT 'PENDING/EXECUTING/DONE/CANCELLED/EXPIRED/FAILED',
    expires_at   DATETIME     NOT NULL COMMENT '提案有效期,PENDING 超时判 EXPIRED',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME     NULL COMMENT '用户确认时间',
    finished_at  DATETIME     NULL COMMENT '副作用执行完成时间',
    PRIMARY KEY (id),
    KEY idx_session (session_id),
    KEY idx_status_expires (status, expires_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '待确认提案状态机';

-- 5. 幂等键(防写操作重复提交)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    idem_key      VARCHAR(128) NOT NULL COMMENT '客户端生成的幂等键(UUID)',
    scope         VARCHAR(64)  NOT NULL COMMENT '业务域:cancel_order/deduct 等',
    user_id       VARCHAR(64)  NOT NULL,
    request_hash  CHAR(64)     NULL COMMENT '请求体 SHA-256,防同键不同参',
    response_body TEXT         NULL COMMENT '首次执行的响应,冲突时原样返回',
    status        VARCHAR(16)  NOT NULL DEFAULT 'PROCESSING' COMMENT 'PROCESSING/DONE',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_idem_key (idem_key),
    KEY idx_expires (expires_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '幂等键';

-- ============================================================
-- 种子数据(供 D3-4 查询联调)
-- ============================================================
INSERT INTO products (spu_code, name, brand, status) VALUES
('SPU-1001', '机械键盘 87 键', 'Keychron', 'online');

INSERT INTO skus (sku_code, product_id, spec_info, price, stock) VALUES
('SKU-1001-A', 1, JSON_OBJECT('color', '黑', 'switch', '红轴'), 299.00, 50),
('SKU-1001-B', 1, JSON_OBJECT('color', '白', 'switch', '茶轴'), 319.00, 30);

INSERT INTO orders (order_no, user_id, total_amount, discount_amount, pay_amount,
                    pay_status, order_status, buyer_remark) VALUES
('SO20260914000001', 1, 299.00, 0.00, 299.00, 'paid', 'shipped', '尽快发货');
INSERT INTO order_items (order_id, sku_id, product_name, unit_price, quantity, total_price) VALUES
(1, 1, '机械键盘 87 键', 299.00, 1, 299.00);

-- 6. 交易 Outbox(本地消息表:支付成功事件同事务落库,定时投递,指数退避)
CREATE TABLE IF NOT EXISTS outbox_events (
    id             BIGINT       NOT NULL AUTO_INCREMENT,
    event_type     VARCHAR(64)  NOT NULL COMMENT 'payment.paid/...',
    aggregate_no   VARCHAR(64)  NOT NULL COMMENT '业务单号',
    payload        JSON         NULL,
    status         VARCHAR(16)  NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/SENT/FAILED',
    retry_count    INT          NOT NULL DEFAULT 0,
    next_retry_at  DATETIME     NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at        DATETIME     NULL,
    PRIMARY KEY (id),
    KEY idx_status_retry (status, next_retry_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易 Outbox';
