package com.csagent.order.controller;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.dto.CreateProposalRequest;
import com.csagent.order.dto.ProposalVO;
import com.csagent.order.service.ProposalService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
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
 * 提案接口:创建(挂在订单路径下)/ 查询 / 确认 / 取消。
 */
@Validated
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ProposalController {

    private final ProposalService proposalService;

    @PostMapping("/orders/{orderId}/cancel-proposal")
    public ApiResponse<ProposalVO> createCancelProposal(
            @PathVariable @Min(1) long orderId,
            @Valid @RequestBody CreateProposalRequest request) {
        return ApiResponse.ok(proposalService.createCancelProposal(orderId, request.sessionId(), request.userId()));
    }

    @GetMapping("/pending-actions/{id}")
    public ApiResponse<ProposalVO> get(@PathVariable @Min(1) long id) {
        return ApiResponse.ok(proposalService.get(id));
    }

    @PostMapping("/pending-actions/{id}/confirm")
    public ApiResponse<ProposalVO> confirm(@PathVariable @Min(1) long id) {
        return ApiResponse.ok(proposalService.confirm(id));
    }

    @PostMapping("/pending-actions/{id}/cancel")
    public ApiResponse<ProposalVO> cancel(@PathVariable @Min(1) long id) {
        return ApiResponse.ok(proposalService.cancel(id));
    }
}
