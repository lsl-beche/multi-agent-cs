package com.csagent.order.it;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.service.InventoryService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 扣减:正常/不足/不存在 + 20 并发零超卖。 */
class InventoryDeductIntegrationTest extends com.csagent.order.support.IntegrationTestBase {

    @Autowired
    InventoryService inventoryService;

    @Autowired
    JdbcTemplate jdbc;

    private void setStock(long skuId, int stock) {
        jdbc.update("UPDATE skus SET stock = ? WHERE id = ?", stock, skuId);
    }

    @Test
    void deduct_success_and_remaining() {
        setStock(1L, 5);
        var result = inventoryService.deduct(1L, 2);
        assertThat(result.remaining()).isEqualTo(3);
    }

    @Test
    void deduct_insufficient() {
        setStock(1L, 1);
        assertThatThrownBy(() -> inventoryService.deduct(1L, 2))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.INSUFFICIENT_STOCK));
    }

    @Test
    void deduct_skuNotFound() {
        assertThatThrownBy(() -> inventoryService.deduct(99999L, 1))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.SKU_NOT_FOUND));
    }

    @Test
    void concurrent_deduct_noOversell() throws Exception {
        final int initial = 10;
        setStock(1L, initial);
        int threads = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger ok = new AtomicInteger();
        AtomicInteger insufficient = new AtomicInteger();

        for (int i = 0; i < threads; i++) {
            pool.submit(() -> {
                start.await();
                try {
                    inventoryService.deduct(1L, 1);
                    ok.incrementAndGet();
                } catch (BusinessException ex) {
                    if (ex.getErrorCode() == ErrorCode.INSUFFICIENT_STOCK) {
                        insufficient.incrementAndGet();
                    }
                }
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(30, java.util.concurrent.TimeUnit.SECONDS);

        Integer finalStock = jdbc.queryForObject("SELECT stock FROM skus WHERE id = 1", Integer.class);
        assertThat(finalStock).isZero();
        assertThat(ok.get()).isEqualTo(initial);
        assertThat(insufficient.get()).isEqualTo(threads - initial);
    }
}
