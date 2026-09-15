package com.csagent.order.it;

import com.csagent.order.support.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 缓存三防验证:命中回填、空值缓存防穿透、写后删(Cache Aside)。
 */
class InventoryCacheIntegrationTest extends IntegrationTestBase {

    @Autowired
    TestRestTemplate rest;

    @Autowired
    StringRedisTemplate redis;

    @Test
    void hit_backfills_cache() {
        rest.getForEntity("/api/inventory/1", String.class);
        assertThat(redis.opsForValue().get("inv:stock:1")).isNotNull();
        // 第二次仍正确(来自缓存)
        ResponseEntity<String> r = rest.getForEntity("/api/inventory/1", String.class);
        assertThat(r.getStatusCode().value()).isEqualTo(200);
    }

    @Test
    void penetration_blocked_by_null_cache() {
        ResponseEntity<String> first = rest.getForEntity("/api/inventory/999999", String.class);
        ResponseEntity<String> second = rest.getForEntity("/api/inventory/999999", String.class);
        assertThat(first.getStatusCode().value()).isEqualTo(404);
        assertThat(second.getStatusCode().value()).isEqualTo(404);
        // 空值哨兵已写入:反复请求不存在的 SKU 不再打库
        String cached = redis.opsForValue().get("inv:stock:999999");
        assertThat(cached).isEqualTo("NULL");
    }

    @Test
    void deduct_evicts_cache() {
        rest.getForEntity("/api/inventory/1", String.class);          // 回填
        assertThat(redis.opsForValue().get("inv:stock:1")).isNotNull();

        HttpHeadersPost post = new HttpHeadersPost(rest);
        post.deduct(1L, 1);                                           // 写操作

        assertThat(redis.opsForValue().get("inv:stock:1")).isNull();  // Cache Aside 删缓存
    }

    /** 小封装避免测试类里堆样板代码。 */
    static class HttpHeadersPost {
        private final TestRestTemplate rest;

        HttpHeadersPost(TestRestTemplate rest) {
            this.rest = rest;
        }

        void deduct(long skuId, int qty) {
            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            headers.set("Idempotency-Key", java.util.UUID.randomUUID().toString());
            rest.postForEntity("/api/inventory/" + skuId + "/deduct",
                    new HttpEntity<>("{\"quantity\":" + qty + "}", headers), String.class);
        }
    }
}
