package com.csagent.order.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

/**
 * 创建订单请求(单 SKU)。购物车多品下单 Phase 2 支持批量原子扣减,
 * 当前多次调用即可——每单一独立幂等键。
 */
public record CreateOrderRequest(
        @NotNull @Positive Long userId,
        @NotNull @Positive Long skuId,
        @NotNull @Min(1) @Max(100) Integer quantity,
        String buyerRemark) {
}
