package com.csagent.order.it;

import com.csagent.order.dto.CreateOrderRequest;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.service.OrderCommandService;
import com.csagent.order.service.OutboxDispatcher;
import com.csagent.order.support.IntegrationTestBase;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Outbox 最终一致性:支付成功与事件同事务落库 → 投递器消费 → SENT;
 * 未配置 webhook 时由日志消费者消费(演示形态)。
 */
class OutboxIntegrationTest extends IntegrationTestBase {

    @Autowired
    OrderCommandService commandService;

    @Autowired
    OutboxDispatcher dispatcher;

    @org.springframework.beans.factory.annotation.Autowired
    com.csagent.order.mapper.OutboxEventMapper outboxEventMapper;

    @Autowired
    JdbcTemplate jdbc;

    private final List<String> createdOrderNos = new ArrayList<>();

    @BeforeEach
    void cleanupResidue() {
        jdbc.update("DELETE FROM outbox_events WHERE aggregate_no LIKE 'SO-IT-%'");
        jdbc.update("DELETE FROM pending_actions WHERE session_id LIKE 'it-%'");
        jdbc.update("DELETE FROM orders WHERE order_no LIKE 'SO-IT-%'");
        jdbc.update("UPDATE skus SET stock = 100 WHERE id = 1");
    }

    private OrderVO createAndPay() {
        OrderVO order = commandService.create(new CreateOrderRequest(9L, 1L, 1, "it"));
        createdOrderNos.add(order.orderNo());
        return commandService.markPaid(
                jdbc.queryForObject("SELECT id FROM orders WHERE order_no = ?", Long.class, order.orderNo()),
                "TRADE-OB", order.payAmount().doubleValue());
    }

    private String inClause() {
        return createdOrderNos.stream().map(n -> "'" + n + "'")
                .reduce((a, b) -> a + "," + b).orElse("'none'");
    }

    @Test
    void mark_paid_writes_outbox_in_same_flow() {
        createAndPay();
        Integer pending = jdbc.queryForObject(
                "SELECT COUNT(*) FROM outbox_events WHERE aggregate_no IN (" + inClause() + ") "
                        + "AND status = 'PENDING'", Integer.class);
        assertThat(pending).isEqualTo(1);   // 事件与业务同事务落库
    }

    @Test
    void dispatcher_delivers_and_marks_sent() {
        createAndPay();
        createAndPay();

        int processed = dispatcher.dispatchDue();

        assertThat(processed).isGreaterThanOrEqualTo(2);
        Integer sent = jdbc.queryForObject(
                "SELECT COUNT(*) FROM outbox_events WHERE aggregate_no IN (" + inClause() + ") "
                        + "AND status = 'SENT'", Integer.class);
        assertThat(sent).isEqualTo(2);
    }

    @Test
    void failed_backoff_schedules_retry() {
        OrderVO order = createAndPay();
        long orderId = jdbc.queryForObject(
                "SELECT id FROM orders WHERE order_no = ?", Long.class, order.orderNo());

        // 模拟投递失败:置 EXECUTING 后标记失败,断言指数退避字段回写
        jdbc.update("UPDATE outbox_events SET status = 'EXECUTING' WHERE aggregate_no = ?", order.orderNo());
        Long eventId = jdbc.queryForObject(
                "SELECT id FROM outbox_events WHERE aggregate_no = ? AND status = 'EXECUTING'",
                Long.class, order.orderNo());
        assertThat(eventId).isNotNull();

        outboxEventMapper.markFailedWithBackoff(eventId);

        Map<String, Object> row = jdbc.queryForMap(
                "SELECT status, retry_count, next_retry_at FROM outbox_events WHERE id = ?", eventId);
        assertThat(row.get("status")).isEqualTo("FAILED");
        assertThat(row.get("retry_count")).isEqualTo(1);
        assertThat(row.get("next_retry_at")).isNotNull();
    }

    @Test
    void dispatcher_is_idempotent_on_empty_queue() {
        dispatcher.dispatchDue();
        int processed = dispatcher.dispatchDue();
        assertThat(processed).isZero();   // 无到期事件,空转无害
    }
}
