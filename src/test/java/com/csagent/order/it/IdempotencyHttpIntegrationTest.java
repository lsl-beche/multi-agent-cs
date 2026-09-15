package com.csagent.order.it;

import com.csagent.order.support.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 幂等键 HTTP 层验证:回放字节一致、失败释放、键体不匹配 40002。
 */
class IdempotencyHttpIntegrationTest extends IntegrationTestBase {

    @Autowired
    TestRestTemplate rest;

    @Autowired
    JdbcTemplate jdbc;

    private ResponseEntity<String> deduct(long skuId, int quantity, String idemKey) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Idempotency-Key", idemKey);
        return rest.postForEntity("/api/inventory/" + skuId + "/deduct",
                new HttpEntity<>("{\"quantity\":" + quantity + "}", headers), String.class);
    }

    private int stock(long skuId) {
        Integer s = jdbc.queryForObject("SELECT stock FROM skus WHERE id = ?", Integer.class, skuId);
        return s == null ? -1 : s;
    }

    @Test
    void replay_identical_and_single_effect() {
        jdbc.update("UPDATE skus SET stock = 5 WHERE id = 2");
        String key = UUID.randomUUID().toString();

        ResponseEntity<String> first = deduct(2L, 1, key);
        ResponseEntity<String> replay = deduct(2L, 1, key);

        assertThat(first.getStatusCode().value()).isEqualTo(200);
        assertThat(replay.getStatusCode().value()).isEqualTo(200);
        assertThat(replay.getHeaders().getFirst("Idempotent-Replayed")).isEqualTo("true");
        assertThat(replay.getBody()).isEqualTo(first.getBody());   // 字节级一致
        assertThat(stock(2L)).isEqualTo(4);                        // 副作用仅一次

        // 同键不同参:客户端 bug 显式拒绝
        ResponseEntity<String> mismatch = deduct(2L, 2, key);
        assertThat(mismatch.getStatusCode().value()).isEqualTo(400);
        assertThat(mismatch.getBody()).contains("40002");
    }

    @Test
    void failure_releases_key_for_retry() {
        jdbc.update("UPDATE skus SET stock = 1 WHERE id = 2");
        String key = UUID.randomUUID().toString();

        // 第一次:数量 5 > 库存 1,业务失败(4xx)
        ResponseEntity<String> fail = deduct(2L, 5, key);
        assertThat(fail.getStatusCode().value()).isEqualTo(409);

        // 同键重试:键已释放,合法请求应重新执行而非回放错误
        ResponseEntity<String> retry = deduct(2L, 1, key);
        assertThat(retry.getStatusCode().value()).isEqualTo(200);
        assertThat(stock(2L)).isZero();
    }
}
