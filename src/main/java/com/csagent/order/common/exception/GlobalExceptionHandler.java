package com.csagent.order.common.exception;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * 全局异常处理:业务异常按错误码返回;参数校验归一为 400;
 * 未预期异常只对外返回"系统繁忙",完整堆栈仅进日志(不向客户端泄漏内部细节)。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> business(BusinessException ex) {
        return build(ex.getErrorCode(), ex.getMessage());
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, HandlerMethodValidationException.class})
    public ResponseEntity<ApiResponse<Void>> invalidParam(Exception ex) {
        String detail = "";
        if (ex instanceof MethodArgumentNotValidException manv) {
            FieldError fe = manv.getBindingResult().getFieldError();
            detail = fe == null ? "" : fe.getField() + " " + fe.getDefaultMessage();
        }
        return build(ErrorCode.PARAM_INVALID, detail.isEmpty() ? null : detail);
    }

    /**
     * 类级 @Validated 时参数校验走 AOP(MethodValidationInterceptor),
     * 抛 jakarta ConstraintViolationException 而非 Spring 内建的 HandlerMethodValidationException,
     * 两条路径都要接,否则参数错误会漏成 500。
     */
    @ExceptionHandler(jakarta.validation.ConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Void>> constraintViolation(jakarta.validation.ConstraintViolationException ex) {
        String detail = ex.getConstraintViolations().stream()
                .map(v -> v.getPropertyPath() + " " + v.getMessage())
                .findFirst().orElse(null);
        return build(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiResponse<Void>> typeMismatch(MethodArgumentTypeMismatchException ex) {
        return build(ErrorCode.PARAM_INVALID, ex.getName() + " 格式错误");
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> noResource(NoResourceFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error(40400, "资源不存在"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> unexpected(Exception ex) {
        log.error("未预期异常", ex);
        return build(ErrorCode.INTERNAL_ERROR, null);
    }

    private ResponseEntity<ApiResponse<Void>> build(ErrorCode errorCode, String message) {
        String msg = message == null || message.isBlank() ? errorCode.defaultMessage() : message;
        return ResponseEntity.status(errorCode.httpStatus())
                .body(ApiResponse.error(errorCode.code(), msg));
    }
}
