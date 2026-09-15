package com.csagent.order.dto;

import com.csagent.order.entity.Order;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 订单视图对象:对外不暴露 version 等内部字段;
 * 当前范围未建 order_items 表,详情仅到订单主档(设计决策见 README)。
 */
public record OrderVO(
        String orderNo,
        Long userId,
        BigDecimal totalAmount,
        BigDecimal discountAmount,
        BigDecimal payAmount,
        String payStatus,
        String orderStatus,
        String buyerRemark,
        LocalDateTime createdAt,
        LocalDateTime paidAt,
        LocalDateTime cancelledAt) {

    public static OrderVO from(Order o) {
        return new OrderVO(o.getOrderNo(), o.getUserId(), o.getTotalAmount(), o.getDiscountAmount(),
                o.getPayAmount(), o.getPayStatus(), o.getOrderStatus(), o.getBuyerRemark(),
                o.getCreatedAt(), o.getPaidAt(), o.getCancelledAt());
    }
}
