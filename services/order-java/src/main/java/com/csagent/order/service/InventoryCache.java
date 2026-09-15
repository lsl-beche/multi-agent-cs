package com.csagent.order.service;

import com.csagent.order.entity.Sku;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.concurrent.ThreadLocalRandom;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * 库存缓存(Cache Aside + 三防):
 * - 穿透:空值缓存(NULL 哨兵,短 TTL),不存在的 SKU 不再反复打库;
 * - 击穿:重建加互斥锁(SET NX + double check),非持锁者短暂等待;
 * - 雪崩:TTL 随机抖动,避免同时失效;
 * - Redis 故障:fail-open,全部降级直查 DB(缓存只是加速层,不是依赖)。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class InventoryCache {

    public record CachedStock(String skuCode, int stock, String status) {
    }

    public record Read(CachedStock value, Result result) {
    }

    public enum Result { HIT, NULL_CACHED, MISS }

    private static final String STOCK_KEY = "inv:stock:";
    private static final String LOCK_KEY = "inv:lock:";
    private static final String NULL_VALUE = "NULL";
    private static final int TTL_BASE = 30;
    private static final int TTL_JITTER = 30;
    private static final int NULL_TTL = 60;
    private static final int LOCK_SECONDS = 10;

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public Read read(long skuId) {
        try {
            String v = redis.opsForValue().get(STOCK_KEY + skuId);
            if (v == null) {
                return new Read(null, Result.MISS);
            }
            if (NULL_VALUE.equals(v)) {
                return new Read(null, Result.NULL_CACHED);
            }
            return new Read(objectMapper.readValue(v, CachedStock.class), Result.HIT);
        } catch (Exception e) {
            log.warn("库存缓存读取失败,降级 DB: {}", e.getMessage());
            return new Read(null, Result.MISS);
        }
    }

    public void putStock(long skuId, CachedStock value) {
        try {
            long ttl = TTL_BASE + ThreadLocalRandom.current().nextLong(TTL_JITTER);
            redis.opsForValue().set(STOCK_KEY + skuId,
                    objectMapper.writeValueAsString(value), Duration.ofSeconds(ttl));
        } catch (Exception e) {
            log.warn("库存缓存写入失败(不影响主流程): {}", e.getMessage());
        }
    }

    public void putNull(long skuId) {
        try {
            redis.opsForValue().set(STOCK_KEY + skuId, NULL_VALUE, Duration.ofSeconds(NULL_TTL));
        } catch (Exception e) {
            log.warn("空值缓存写入失败(不影响主流程): {}", e.getMessage());
        }
    }

    public void evict(long skuId) {
        try {
            redis.delete(STOCK_KEY + skuId);
        } catch (Exception e) {
            log.warn("库存缓存删除失败(不影响主流程): {}", e.getMessage());
        }
    }

    /** 重建互斥锁:SET NX EX;抢到者重建,未抢到者等待重读。 */
    public boolean tryLock(long skuId) {
        try {
            return Boolean.TRUE.equals(redis.opsForValue()
                    .setIfAbsent(LOCK_KEY + skuId, "1", Duration.ofSeconds(LOCK_SECONDS)));
        } catch (Exception e) {
            return true;   // Redis 故障时放行为"持锁者",退化为主流直查路径
        }
    }

    public void unlock(long skuId) {
        try {
            redis.delete(LOCK_KEY + skuId);
        } catch (Exception ignored) {
        }
    }
}
