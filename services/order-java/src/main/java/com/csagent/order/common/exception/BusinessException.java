package com.csagent.order.common.exception;

import com.csagent.order.common.ErrorCode;

/** 业务异常:携带错误码,由 GlobalExceptionHandler 统一转为 ApiResponse。 */
public class BusinessException extends RuntimeException {

    private final ErrorCode errorCode;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.defaultMessage());
        this.errorCode = errorCode;
    }

    public BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public ErrorCode getErrorCode() {
        return errorCode;
    }
}
