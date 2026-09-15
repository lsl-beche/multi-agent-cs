package com.csagent.order.controller;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.PageResult;
import com.csagent.order.dto.CreateOrderRequest;
import com.csagent.order.dto.MarkPaidRequest;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.service.OrderCommandService;
import com.csagent.order.service.OrderQueryService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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
    private final OrderCommandService orderCommandService;

    /** 创建订单(单 SKU):原子扣减 + 订单/商品行同事务落库;幂等键由过滤器覆盖。 */
    @PostMapping
    public ApiResponse<OrderVO> create(@Valid @RequestBody CreateOrderRequest request) {
        return ApiResponse.ok(orderCommandService.create(request));
    }

    /** 支付成功标记:金额强校验,回调重放幂等。 */
    @PostMapping("/{id}/paid")
    public ApiResponse<OrderVO> markPaid(@PathVariable @Min(1) long id,
                                         @Valid @RequestBody MarkPaidRequest request) {
        return ApiResponse.ok(orderCommandService.markPaid(id, request.tradeNo(), request.amount()));
    }

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
