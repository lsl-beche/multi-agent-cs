package com.csagent.order.controller;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.PageResult;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.service.OrderQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 订单查询接口(供 Python CSagent 与管理后台调用)。
 * 分页 size 上限 50:防止大页拖垮 DB。
 */
@Validated
@RestController
@RequestMapping("/api/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderQueryService orderQueryService;

    @GetMapping("/{id}")
    public ApiResponse<OrderVO> detail(@PathVariable @Min(1) long id) {
        return ApiResponse.ok(orderQueryService.getById(id));
    }

    /** 按业务单号换算本服务订单 ID(Python 智能层单号为字符串)。 */
    @GetMapping("/by-no/{orderNo}")
    public ApiResponse<Long> idByOrderNo(@PathVariable String orderNo) {
        return ApiResponse.ok(orderQueryService.getIdByOrderNo(orderNo));
    }

    @GetMapping
    public ApiResponse<PageResult<OrderVO>> page(
            @RequestParam @Positive long userId,
            @RequestParam(required = false) String orderStatus,
            @RequestParam(required = false) String payStatus,
            @RequestParam(defaultValue = "1") @Min(1) int page,
            @RequestParam(defaultValue = "10") @Min(1) @Max(50) int size) {
        return ApiResponse.ok(orderQueryService.page(userId, orderStatus, payStatus, page, size));
    }
}
