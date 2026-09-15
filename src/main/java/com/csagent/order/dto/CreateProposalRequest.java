package com.csagent.order.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;

/** 创建取消提案请求。无鉴权阶段 sessionId/userId 由调用方(Python Agent)透传。 */
public record CreateProposalRequest(
        @NotBlank String sessionId,
        @Positive long userId) {
}
