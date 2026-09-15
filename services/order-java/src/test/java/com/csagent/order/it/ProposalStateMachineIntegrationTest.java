package com.csagent.order.it;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.service.ProposalService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 提案状态机全路径 + 并发确认恰好一次(20 线程抢同一提案)。
 * 对拍事实:Python 侧 check-then-act 实现已复现 20 次重复执行(README D8-9)。
 */
class ProposalStateMachineIntegrationTest extends com.csagent.order.support.IntegrationTestBase {

    @Autowired
    ProposalService proposalService;

    @Autowired
    JdbcTemplate jdbc;

    /** 固定单号/会话 ID 的测试需要可重跑:每次先清掉本类的残留数据。 */
    @BeforeEach
    void cleanupResidue() {
        jdbc.update("DELETE FROM pending_actions WHERE session_id LIKE 'it-%'");
        jdbc.update("DELETE FROM orders WHERE order_no LIKE 'SO-IT-%'");
    }

    private long insertOrder(String orderNo) {
        jdbc.update("INSERT INTO orders (order_no,user_id,total_amount,discount_amount,pay_amount,order_status) "
                + "VALUES (?,1,1.00,0,1.00,'pending')", orderNo);
        return jdbc.queryForObject("SELECT id FROM orders WHERE order_no = ?", Long.class, orderNo);
    }

    private long insertProposal(long orderId, String sessionId, String expiresClause) {
        jdbc.update("INSERT INTO pending_actions (session_id,user_id,action_type,order_id,status,expires_at) "
                + "VALUES (?,1,'CANCEL_ORDER',?,'PENDING',NOW() + " + expiresClause + ")",
                sessionId, orderId);
        return jdbc.queryForObject(
                "SELECT id FROM pending_actions WHERE session_id = ?", Long.class, sessionId);
    }

    private Map<String, Object> orderRow(long orderId) {
        return jdbc.queryForMap("SELECT order_status, version FROM orders WHERE id = ?", orderId);
    }

    @Test
    void create_confirm_cancelFlow() {
        long orderId = insertOrder("SO-IT-A1");
        var proposal = proposalService.createCancelProposal(orderId, "it-a1", 1L);
        assertThat(proposal.status()).isEqualTo("PENDING");

        var done = proposalService.confirm(proposal.id());
        assertThat(done.status()).isEqualTo("DONE");

        var order = orderRow(orderId);
        assertThat(order.get("order_status")).isEqualTo("cancelled");
        assertThat(order.get("version")).isEqualTo(2);   // 初始 1 + 副作用恰好 +1

        // 已取消订单不能再创建提案
        assertThatThrownBy(() -> proposalService.createCancelProposal(orderId, "it-a1b", 1L))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.ORDER_ALREADY_CANCELLED));
    }

    @Test
    void cancel_then_confirm_conflict() {
        long orderId = insertOrder("SO-IT-A2");
        long actionId = insertProposal(orderId, "it-a2", "INTERVAL 10 MINUTE");

        proposalService.cancel(actionId);
        assertThatThrownBy(() -> proposalService.confirm(actionId))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.PENDING_ACTION_CONFLICT));
    }

    @Test
    void confirm_expired() {
        long orderId = insertOrder("SO-IT-A3");
        long actionId = insertProposal(orderId, "it-a3", "INTERVAL -5 MINUTE");   // 已过期

        // 对账任务可能已归档:410(未归档)或 409(已归档为 EXPIRED)都算正确
        try {
            proposalService.confirm(actionId);
            throw new AssertionError("过期提案确认应失败");
        } catch (BusinessException ex) {
            assertThat(ex.getErrorCode()).isIn(ErrorCode.PENDING_ACTION_EXPIRED, ErrorCode.PENDING_ACTION_CONFLICT);
        }
    }

    @Test
    void concurrent_confirm_exactlyOnce() throws Exception {
        long orderId = insertOrder("SO-IT-A4");
        long actionId = insertProposal(orderId, "it-a4", "INTERVAL 10 MINUTE");

        int threads = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger success = new AtomicInteger();
        var errors = new ConcurrentHashMap<ErrorCode, Integer>();

        for (int i = 0; i < threads; i++) {
            pool.submit(() -> {
                start.await();
                try {
                    proposalService.confirm(actionId);
                    success.incrementAndGet();
                } catch (BusinessException ex) {
                    errors.merge(ex.getErrorCode(), 1, Integer::sum);
                }
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(30, java.util.concurrent.TimeUnit.SECONDS);

        var order = orderRow(orderId);
        assertThat(success.get()).isEqualTo(1);                       // 恰好一个确认成功
        assertThat(order.get("version")).isEqualTo(2);                // 副作用恰好一次
        assertThat(order.get("order_status")).isEqualTo("cancelled");
        assertThat(errors.keySet()).containsOnly(ErrorCode.PENDING_ACTION_CONFLICT);
    }
}
