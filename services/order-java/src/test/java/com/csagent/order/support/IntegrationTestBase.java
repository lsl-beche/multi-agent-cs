package com.csagent.order.support;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.utility.MountableFile;

/**
 * 集成测试数据库策略(双路):
 * 1. -Dtestcontainers=true:单例 MySQL Testcontainers,挂载生产同源 db/schema.sql;
 *    注:本机 Docker Desktop 29.x 引擎 API 与 testcontainers 1.19.x 存在兼容问题
 *    (占位 400),升级 testcontainers 后启用;
 * 2. 默认:回落 Compose MySQL(localhost:3306/order_service,先 docker compose down -v && up
 *    保证 schema+种子与生产同源)。测试各自清理/重置自己触达的数据。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public abstract class IntegrationTestBase {

    static final boolean USE_TESTCONTAINERS =
            Boolean.parseBoolean(System.getProperty("testcontainers", "false"));

    static final MySQLContainer<?> MYSQL = USE_TESTCONTAINERS ? buildAndStart() : null;

    static MySQLContainer<?> buildAndStart() {
        // schema 走 classpath(src/test/resources/order-schema.sql,与工作目录无关);
        // 主副本在 db/schema.sql 供 compose init,两处需同步。
        MySQLContainer<?> container = new MySQLContainer<>("mysql:8.0")
                .withDatabaseName("order_service")
                .withUsername("root")
                .withPassword("order_dev_2026")
                .withCopyFileToContainer(
                        MountableFile.forClasspathResource("order-schema.sql"),
                        "/docker-entrypoint-initdb.d/01-schema.sql");
        container.start();
        return container;
    }

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        if (USE_TESTCONTAINERS) {
            registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
            registry.add("spring.datasource.username", MYSQL::getUsername);
            registry.add("spring.datasource.password", MYSQL::getPassword);
        } else {
            registry.add("spring.datasource.url", () ->
                    "jdbc:mysql://localhost:3306/order_service?useUnicode=true&characterEncoding=utf8"
                            + "&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true");
            registry.add("spring.datasource.username", () -> "root");
            registry.add("spring.datasource.password", () -> "order_dev_2026");
        }
    }
}
