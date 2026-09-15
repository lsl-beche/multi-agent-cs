package com.csagent.order.dto;

import com.csagent.order.entity.Order;
import com.csagent.order.entity.Order;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 订单视图对象:对外不暴露 version 等内部字段;items 为商品行快照。
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
        LocalDateTime cancelledAt,
        List<ItemVO> items) {

    public record ItemVO(String productName, BigDecimal unitPrice, int quantity, BigDecimal totalPrice) {
    }

    public static OrderVO from(Order o) {
        return from(o, List.of());
    }

    public static OrderVO from(Order o, List<ItemVO> items) {
        return new OrderVO(o.getOrderNo(), o.getUserId(), o.getTotalAmount(), o.getDiscountAmount(),
                o.getPayAmount(), o.getPayStatus(), o.getOrderStatus(), o.getBuyerRemark(),
                o.getCreatedAt(), o.getPaidAt(), o.getCancelledAt(), items);
    }
}
