package com.csagent.order.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

/** 支付成功标记(回调/智能层驱动):金额与订单应付的一致性在服务端强校验。 */
public record MarkPaidRequest(
        @NotBlank String tradeNo,
        @NotNull @Positive Double amount) {
}
