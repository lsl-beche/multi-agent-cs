package com.csagent.order.controller;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.dto.DeductRequest;
import com.csagent.order.dto.DeductResult;
import com.csagent.order.dto.InventoryVO;
import com.csagent.order.service.InventoryService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 库存接口:写操作(D5-6 原子扣减);幂等键由 D10 的拦截器统一接入本路由。
 */
@Validated
@RestController
@RequestMapping("/api/inventory")
@RequiredArgsConstructor
public class InventoryController {

    private final InventoryService inventoryService;

    @GetMapping("/{skuId}")
    public ApiResponse<InventoryVO> stock(@PathVariable @Min(1) long skuId) {
        return ApiResponse.ok(inventoryService.getStock(skuId));
    }

    @PostMapping("/{skuId}/deduct")
    public ApiResponse<DeductResult> deduct(@PathVariable @Min(1) long skuId,
                                            @Valid @RequestBody DeductRequest request) {
        return ApiResponse.ok(inventoryService.deduct(skuId, request.quantity()));
    }
}
