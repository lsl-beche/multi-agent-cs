package com.csagent.order.it;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.CreateOrderRequest;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.service.OrderCommandService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 订单全生命周期:创建(原子扣减+商品行快照)→ 支付(金额校验+重放幂等)→ 取消。
 */
class OrderLifecycleIntegrationTest extends com.csagent.order.support.IntegrationTestBase {

    @Autowired
    OrderCommandService commandService;

    @Autowired
    JdbcTemplate jdbc;

    @BeforeEach
    void cleanupResidue() {
        jdbc.update("DELETE FROM order_items WHERE order_id IN "
                + "(SELECT id FROM orders WHERE order_no LIKE 'SO-IT-%')");
        jdbc.update("DELETE FROM pending_actions WHERE session_id LIKE 'it-%'");
        jdbc.update("DELETE FROM orders WHERE order_no LIKE 'SO-IT-%'");
    }

    private OrderVO create(int qty) {
        return commandService.create(new CreateOrderRequest(9L, 1L, qty, "it"));
    }

    @Test
    void create_deducts_stock_and_snapshots_item() {
        jdbc.update("UPDATE skus SET stock = 10 WHERE id = 1");
        OrderVO vo = create(2);

        assertThat(vo.orderNo()).startsWith("SO");
        assertThat(vo.payAmount().doubleValue()).isEqualTo(598.0);   // 299 × 2
        assertThat(vo.items()).hasSize(1);
        assertThat(vo.items().get(0).productName()).isEqualTo("机械键盘 87 键");

        Integer stock = jdbc.queryForObject("SELECT stock FROM skus WHERE id = 1", Integer.class);
        assertThat(stock).isEqualTo(8);                              // 原子扣减
        Integer itemCount = jdbc.queryForObject(
                "SELECT COUNT(*) FROM order_items WHERE order_id = "
                        + "(SELECT id FROM orders WHERE order_no = ?)", Integer.class, vo.orderNo());
        assertThat(itemCount).isEqualTo(1);
    }

    @Test
    void create_insufficient_stock() {
        jdbc.update("UPDATE skus SET stock = 1 WHERE id = 1");
        assertThatThrownBy(() -> create(2))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.INSUFFICIENT_STOCK));
        Integer stock = jdbc.queryForObject("SELECT stock FROM skus WHERE id = 1", Integer.class);
        assertThat(stock).isEqualTo(1);                              // 未误扣
    }

    @Test
    void paid_flow_idempotent_replay() {
        jdbc.update("UPDATE skus SET stock = 10 WHERE id = 1");
        OrderVO order = create(1);
        long orderId = jdbc.queryForObject(
                "SELECT id FROM orders WHERE order_no = ?", Long.class, order.orderNo());

        OrderVO paid = commandService.markPaid(orderId, "TRADE-IT-1", order.payAmount().doubleValue());
        assertThat(paid.payStatus()).isEqualTo("paid");
        assertThat(paid.orderStatus()).isEqualTo("confirmed");

        // 回调重放:同金额再标一次,状态不变、版本不再增长
        commandService.markPaid(orderId, "TRADE-IT-1", order.payAmount().doubleValue());
        Map<String, Object> row = jdbc.queryForMap(
                "SELECT pay_status, version FROM orders WHERE id = ?", orderId);
        assertThat(row.get("pay_status")).isEqualTo("paid");
        assertThat(row.get("version")).isEqualTo(2);                 // 仅首次 +1
    }

    @Test
    void paid_amount_mismatch_rejected() {
        jdbc.update("UPDATE skus SET stock = 10 WHERE id = 1");
        OrderVO order = create(1);
        long orderId = jdbc.queryForObject(
                "SELECT id FROM orders WHERE order_no = ?", Long.class, order.orderNo());

        assertThatThrownBy(() -> commandService.markPaid(orderId, "TRADE-BAD", 0.01))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.AMOUNT_MISMATCH));

        String payStatus = jdbc.queryForObject(
                "SELECT pay_status FROM orders WHERE id = ?", String.class, orderId);
        assertThat(payStatus).isEqualTo("unpaid");                   // 未被污染
    }

    @Test
    void cancel_unpaid_via_proposal_restores_stock() {
        jdbc.update("UPDATE skus SET stock = 10 WHERE id = 1");
        OrderVO order = create(2);                          // 创建扣减:10 → 8
        long orderId = jdbc.queryForObject(
                "SELECT id FROM orders WHERE order_no = ?", Long.class, order.orderNo());
        long actionId = insertProposal(orderId, "it-lc1", "INTERVAL 10 MINUTE");

        var done = proposalService.confirm(actionId);
        assertThat(done.status()).isEqualTo("DONE");
        assertThat(jdbc.queryForObject(
                "SELECT order_status FROM orders WHERE id = ?", String.class, orderId))
                .isEqualTo("cancelled");
        // 回补断言:取消必须把创建时扣掉的库存还回去(8 → 10)
        Integer stock = jdbc.queryForObject("SELECT stock FROM skus WHERE id = 1", Integer.class);
        assertThat(stock).isEqualTo(10);
    }

    @Autowired
    com.csagent.order.service.ProposalService proposalService;

    private long insertProposal(long orderId, String sessionId, String expiresClause) {
        jdbc.update("INSERT INTO pending_actions (session_id,user_id,action_type,order_id,status,expires_at) "
                + "VALUES (?,1,'CANCEL_ORDER',?,'PENDING',NOW() + " + expiresClause + ")", sessionId, orderId);
        return jdbc.queryForObject(
                "SELECT id FROM pending_actions WHERE session_id = ?", Long.class, sessionId);
    }
}
