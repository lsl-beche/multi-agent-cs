package com.csagent.order.common;

import org.springframework.http.HttpStatus;

/**
 * 业务错误码:前三位对齐 HTTP 状态,后两位细分业务含义。
 */
public enum ErrorCode {
    PARAM_INVALID(40001, HttpStatus.BAD_REQUEST, "参数错误"),
    ORDER_NOT_FOUND(40401, HttpStatus.NOT_FOUND, "订单不存在"),
    SKU_NOT_FOUND(40402, HttpStatus.NOT_FOUND, "SKU 不存在"),
    PENDING_ACTION_NOT_FOUND(40403, HttpStatus.NOT_FOUND, "提案不存在"),
    INSUFFICIENT_STOCK(40901, HttpStatus.CONFLICT, "库存不足"),
    PENDING_ACTION_CONFLICT(40902, HttpStatus.CONFLICT, "提案状态不允许该操作"),
    ORDER_ALREADY_CANCELLED(40903, HttpStatus.CONFLICT, "订单已取消"),
    PENDING_ACTION_EXISTS(40904, HttpStatus.CONFLICT, "已存在待确认提案"),
    PENDING_ACTION_EXPIRED(41001, HttpStatus.GONE, "提案已过期"),
    IDEMPOTENCY_PROCESSING(40905, HttpStatus.CONFLICT, "相同幂等键的请求正在处理中"),
    AMOUNT_MISMATCH(40906, HttpStatus.CONFLICT, "支付金额与订单应付不一致"),
    IDEMPOTENCY_MISMATCH(40002, HttpStatus.BAD_REQUEST, "幂等键与请求体不匹配"),
    INTERNAL_ERROR(50001, HttpStatus.INTERNAL_SERVER_ERROR, "系统繁忙,请稍后重试");

    private final int code;
    private final HttpStatus httpStatus;
    private final String defaultMessage;

    ErrorCode(int code, HttpStatus httpStatus, String defaultMessage) {
        this.code = code;
        this.httpStatus = httpStatus;
        this.defaultMessage = defaultMessage;
    }

    public int code() {
        return code;
    }

    public HttpStatus httpStatus() {
        return httpStatus;
    }

    public String defaultMessage() {
        return defaultMessage;
    }
}
