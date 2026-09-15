package com.csagent.order.dto;

/** 扣减结果:remaining 为扣减后瞬时读数(同事务内读,含行锁,不受并发影响)。 */
public record DeductResult(String skuCode, int deducted, int remaining) {
}
