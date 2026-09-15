package com.csagent.order.dto;

import com.csagent.order.entity.PendingAction;
import java.time.LocalDateTime;

/** 提案视图:状态即契约,调用方据 status 决定下一步。 */
public record ProposalVO(
        long id,
        String sessionId,
        String actionType,
        long orderId,
        String status,
        LocalDateTime expiresAt,
        LocalDateTime createdAt,
        LocalDateTime confirmedAt,
        LocalDateTime finishedAt) {

    public static ProposalVO from(PendingAction a) {
        return new ProposalVO(a.getId(), a.getSessionId(), a.getActionType(), a.getOrderId(),
                a.getStatus(), a.getExpiresAt(), a.getCreatedAt(), a.getConfirmedAt(), a.getFinishedAt());
    }
}
