package com.csagent.order.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

/** 单次扣减数量上限 100:防止单请求打穿库存,具体上限应由业务配置。 */
public record DeductRequest(
        @NotNull @Min(1) @Max(100) Integer quantity) {
}
