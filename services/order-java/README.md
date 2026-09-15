# order-service(CSagent 订单服务 · Java 重写)

CSagent 订单写链路的 Spring Boot 重写:**交易链路用 Java、智能层用 Python(CSagent),REST + 幂等键集成**。

- 项目背景与完整方案:见《CSagent Java 重写方案 v2.0》
- 关联仓库:`E:\workspace\CSagent`(Python 智能层)

## 范围(D1-12 全部完成)

- [x] Spring Boot 3 工程骨架(Web/Validation/MyBatis-Plus/Redis)
- [x] 5 张表:products / skus / orders / pending_actions / idempotency_keys
- [x] Compose 编排 MySQL 8 + Redis 7(schema 自动初始化)
- [x] 订单查询接口(D3-4)
- [x] 乐观锁扣减 + 并发验证(D5-6)
- [x] 提案确认状态机 + 对拍测试(D8-9)
- [x] 幂等键过滤器 + Python 集成客户端(D10)
- [x] 集成测试 13 用例(D11)
- [x] Dockerfile 多阶段构建 + compose full profile 一键全栈(D12)

## 证据汇总

| 验证 | 结果 |
|---|---|
| 20 并发扣减(库存10) | 恰好 10 成功 / 10×409 / 终态 0,零超卖 |
| 500 笔压测(20 线程) | 全部成功,吞吐 ≈43 req/s,守恒 PASS |
| 对拍:20 并发确认 | 原子版副作用恰好 1 次;legacy(复刻 Python 缺陷)20 次 |
| 集成测试(Testcontainers/Compose MySQL) | 13/13 PASS |
| 幂等 HTTP | 回放字节一致 / 键体不匹配 40002 / 失败释放键 |

> 吞吐说明:43 req/s 的瓶颈是热点单行行锁串行化——强一致场景的正确代价;高并发秒杀需引入 Redis 预扣减/削峰,以一致性换吞吐(当前业务量不需要)。

## 快速开始

```bash
# 方式 A:全栈容器化(Java 服务 + MySQL + Redis 一键起)
docker compose --profile full up -d --build

# 方式 B:本机跑服务,Compose 只起依赖
docker compose up -d
mvn package
java -jar target/order-service-0.1.0.jar

# 验证
curl http://localhost:8081/api/health

# 集成测试(13 用例,需 Docker;默认连 Compose MySQL,-Dtestcontainers=true 切 Testcontainers)
mvn test

# 并发/幂等验证脚本
python scripts/concurrency_deduct_test.py --sku-id 1 --qty 1 --threads 20
python scripts/idempotency_test.py --sku 2
```

## 设计决策(边做边记,面试答案手册)

### D1-2 表结构
- **库存合并**:CSagent 把库存独立为 `inventory` 表(多仓 + version 乐观锁);本服务单仓场景,合并 `stock`/`version` 进 `skus`,扣减语义不变(条件 UPDATE 原子防超卖)。
- **提案落库**:Python 侧提案存 Redis(action_store,Redis 故障会丢);Java 侧落 `pending_actions` 表,`PENDING → EXECUTING → DONE/FAILED` 状态机 + `expires_at` 惰性过期,EXECUTING 超时回收防"抢占后崩溃丢副作用"。
- **幂等键独立表**:唯一约束兜底,冲突时返回首次 `response_body`,重试对调用方透明。

### D11-12 集成测试 + 容器化交付
- **集成测试双路**:`-Dtestcontainers=true` 走单例 MySQL Testcontainers(schema 与生产同源挂载);默认回落 Compose MySQL——本机 Docker Desktop 29.x 引擎 API 与 testcontainers 1.19.x 不兼容(占位 400),升级后可切回;
- **测试矩阵(13 用例)**:查询 3 / 扣减含 20 并发零超卖 4 / 状态机全路径含 20 并发恰好一次 4 / 幂等 HTTP 回放-释放-不匹配 2;
- **对拍可复现**:legacy check-then-act 缺陷在 20 并发下稳定复现 20 次重复执行(脚本已入库);
- **容器化**:多阶段构建(Maven 构建 → JRE 21 运行层,非 root 用户),`docker compose --profile full up -d --build` 一键全栈,三容器 healthcheck 齐备。

### D10 幂等键 + Python 集成
- **过滤器统一接入**:受保护 POST 路径带 `Idempotency-Key` 才启用;**Filter 层无 @RestControllerAdvice**,业务异常必须就地写错误 JSON(抛出即 500,实测踩中);
- **语义**:2xx 存档响应供回放;≥4xx 释放键(同键可安全重试);同键不同参 40002(客户端 bug 显式暴露);PROCESSING 冲突 40905;过期 PROCESSING 删除接管(持有者崩溃自愈);
- **响应存档用 TEXT 不用 JSON 列**:MySQL JSON 列会规范化文本(冒号加空格),破坏字节级回放(实测踩中);
- **@MapperScan 扫根包**:独立包的 Mapper 靠 @Mapper 注解识别,只扫 mapper 子包会漏注册;
- **双服务联通**:integration/agent_client.py 是 Python 智能层的生产接入样例(自动幂等键),冒烟通过——扣减重放一致、提案确认后订单 cancelled;
- **order_agent.py 切流**(待做):把写工具的实现替换为 agent_client 调用,查询类工具同理,预计 <20 行改动。

### D8-9 提案状态机 + 对拍测试(核心)
- **状态机**:`PENDING -(原子抢占)- EXECUTING -(副作用+标记DONE 同事务)- DONE`;旁路:CANCELLED(用户撤销)/ EXPIRED(过期)/ FAILED(可重试);
- **抢占即归因**:claim 受影响行数=0 时二次查询,不存在→404、PENDING 已过期→410(惰性归档)、已被对账任务归档/终态→409(附当前状态);
- **EXECUTING 中间态**:防"抢占成功但服务崩溃丢副作用";对账任务 30s 一轮,>60s 的 EXECUTING 回收重抢,**安全性建立在副作用条件化之上**(仅非 cancelled 才变更,重放无害);
- **自调用事务坑**:副作用+标记 DONE 单独成 `ProposalExecutionService` Bean——同类自调用 `@Transactional` 不走代理、事务失效;
- **对拍证据**(同库同 20 并发,各注入一对新订单+提案):

| 指标 | 原子版(条件 UPDATE 抢占) | legacy(check-then-act,复刻 Python 缺陷) |
|---|---|---|
| 200 响应 | **1** | 20 |
| 409 冲突 | **19** | 0 |
| 副作用执行次数(order.version−1) | **1** | **20** |
| 判定 | PASS:恰好一次 | REPRODUCED:竞态复现 |

- 其余路径实测:重复创建提案 409/40904;撤销后确认 409/40902;确认后订单 `cancelled`;
- 复现:`scripts/concurrency_confirm_test.py --action-id <a> --order-id <o> --mode atomic|legacy`(数据准备 SQL 见脚本头)。

### D5-6 乐观锁扣减 + 并发验证
- **原子扣减**:单条条件 UPDATE(`WHERE stock >= n`)把"查→判→减"压缩为一步,InnoDB 行锁串行化并发,受影响行数即结果——1 成功,0 走二次查询区分"不存在(40402)/不足(40901)";
- **事务的真实作用**:不是保证单条 UPDATE 原子(天然原子),而是保证"扣减→回读 remaining"的一致性——UPDATE 行锁持到提交,并发串行排队;
- **并发验证证据**(SKU-1001-A,库存压到 10,20 并发各扣 1):

| 指标 | 期望 | 实测 |
|---|---|---|
| 200 成功 | ≤10 | **10** |
| 409 库存不足 | 10 | **10** |
| 其他响应码 | 0 | **0** |
| 终态库存 | 0 | **0** |
| 守恒律 success×qty = initial−final | 10=10 | **PASS** |

- **边界实测**:不存在 SKU → 404/40402;quantity=0 → 400/40001;
- 复现:`python scripts/concurrency_deduct_test.py --sku-id 1 --qty 1 --threads 20`。

### D3-4 订单查询
- **API 不泄漏 ORM**:响应走 `OrderVO`(去掉 version 等内部字段),分页用自定义 `PageResult`,不暴露 MyBatis-Plus 的 `Page`;
- **分页 size 上限 50**:防大页拖垮 DB;MyBatis-Plus 必须显式注册 `PaginationInnerInterceptor`,否则 selectPage 不加 LIMIT、total 恒为 0;
- **参数校验双路径坑**:类级 `@Validated` 时参数校验走 AOP,抛 `jakarta.validation.ConstraintViolationException`;无 `@Validated` 时 Spring 6.1 内建校验抛 `HandlerMethodValidationException`——全局处理器两条都要接,漏一条参数错误就会变成 500(本次实测踩中);
- **订单详情未展开 order_items**:当前 5 表范围不建子表,详情到订单主档;若后续需要商品行,加 `order_items` 表并联表查询。

## 环境

- JDK 21(便携版):`E:\workspace\tools\jdk-21.0.12.1+1`
- Maven 3.9.16(便携版):`E:\workspace\tools\apache-maven-3.9.16`
- Maven 镜像:Aliyun(`~/.m2/settings.xml`)

PowerShell 会话临时环境变量:
```powershell
$env:JAVA_HOME = "E:\workspace\tools\jdk-21.0.12.1+1"
$env:Path = "$env:JAVA_HOME\bin;E:\workspace\tools\apache-maven-3.9.16\bin;$env:Path"
```
