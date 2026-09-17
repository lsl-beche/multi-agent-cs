package com.csagent.order.it;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.PageResult;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.service.OrderQueryService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 订单查询:命中/未命中/分页。种子数据:订单 1 = SO20260914000001(user_id=1, shipped)。 */
class OrderQueryIntegrationTest extends com.csagent.order.support.IntegrationTestBase {

    @Autowired
    OrderQueryService orderQueryService;

    @Test
    void detail_found() {
        OrderVO vo = orderQueryService.getById(1L);
        assertThat(vo.orderNo()).isEqualTo("SO20260914000001");
        assertThat(vo.payAmount().doubleValue()).isEqualTo(299.00);
    }

    @Test
    void detail_notFound() {
        assertThatThrownBy(() -> orderQueryService.getById(99999L))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.ORDER_NOT_FOUND));
    }

    @Test
    void byNo_found_and_notFound() {
        assertThat(orderQueryService.getIdByOrderNo("SO20260914000001")).isEqualTo(1L);
        assertThatThrownBy(() -> orderQueryService.getIdByOrderNo("SO-NOPE"))
                .isInstanceOfSatisfying(BusinessException.class, ex ->
                        assertThat(ex.getErrorCode()).isEqualTo(ErrorCode.ORDER_NOT_FOUND));
    }

    @Test
    void page_byUser() {
        PageResult<OrderVO> page = orderQueryService.page(1L, null, null, 1, 10);
        assertThat(page.total()).isGreaterThanOrEqualTo(1);
        assertThat(page.records()).allSatisfy(vo -> assertThat(vo.userId()).isEqualTo(1L));
    }
}
