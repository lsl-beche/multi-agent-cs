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
 * 滑动窗口限流:同身份连续请求,超限 429 + Retry-After;不同身份互不影响。
 */
class RateLimitIntegrationTest extends IntegrationTestBase {

    @Autowired
    TestRestTemplate rest;

    @Autowired
    JdbcTemplate jdbc;

    private ResponseEntity<String> deduct(String userId, long skuId) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Idempotency-Key", UUID.randomUUID().toString());
        headers.set("X-User-Id", userId);
        return rest.postForEntity("/api/inventory/" + skuId + "/deduct",
                new HttpEntity<>("{\"quantity\":1}", headers), String.class);
    }

    @Test
    void burst_over_limit_gets_429() {
        jdbc.update("UPDATE skus SET stock = 1000 WHERE id = 1");
        String user = "rl-" + UUID.randomUUID();   // 唯一身份,免受其他用例窗口影响

        int ok = 0, limited = 0;
        for (int i = 0; i < 20; i++) {
            ResponseEntity<String> r = deduct(user, 1L);
            if (r.getStatusCode().value() == 429) {
                limited++;
                assertThat(r.getHeaders().getFirst("Retry-After")).isNotNull();
                assertThat(r.getBody()).contains("42901");
            } else {
                ok++;
            }
        }
        // deduct 限 15/10s:20 连发最多 15 笔执行,其余 429
        assertThat(limited).isGreaterThanOrEqualTo(1);
        assertThat(ok).isLessThanOrEqualTo(15);
    }

    @Test
    void different_users_have_independent_windows() {
        jdbc.update("UPDATE skus SET stock = 1000 WHERE id = 2");
        String u1 = "rl-u1-" + UUID.randomUUID();
        for (int i = 0; i < 15; i++) {
            deduct(u1, 2L);   // 打满 u1 窗口
        }
        ResponseEntity<String> other = deduct("rl-u2-" + UUID.randomUUID(), 2L);
        assertThat(other.getStatusCode().value()).isEqualTo(200);   // 别的账户不受影响
    }
}
