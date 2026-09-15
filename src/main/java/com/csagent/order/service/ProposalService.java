package com.csagent.order.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.ProposalVO;
import com.csagent.order.entity.Order;
import com.csagent.order.entity.PendingAction;
import com.csagent.order.mapper.OrderMapper;
import com.csagent.order.mapper.PendingActionMapper;
import java.time.LocalDateTime;
import java.util.concurrent.ThreadLocalRandom;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 提案状态机:创建/确认/取消/查询。
 *
 * 确认流程 = 原子抢占(claimForExecution)→ 执行副作用 + 标记 DONE(同事务)。
 * 抢占失败时二次查询区分三种原因:不存在(404)/已过期(410)/状态冲突(409)。
 *
 * 事务边界说明:抢占在最前(独立提交,先到先得);副作用与标记 DONE 在
 * ProposalExecutionService 的同一事务里——若副作用是外部调用(HTTP/MQ),
 * 则改为"副作用自身幂等 + EXECUTING 超时回收"兜底,见 README。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ProposalService {

    private static final int PROPOSAL_TTL_MINUTES = 10;

    private final PendingActionMapper pendingActionMapper;
    private final OrderMapper orderMapper;
    private final ProposalExecutionService executionService;

    public ProposalVO createCancelProposal(long orderId, String sessionId, long userId) {
        Order order = orderMapper.selectById(orderId);
        if (order == null) {
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND);
        }
        if ("cancelled".equals(order.getOrderStatus())) {
            throw new BusinessException(ErrorCode.ORDER_ALREADY_CANCELLED);
        }
        Long pending = pendingActionMapper.selectCount(new LambdaQueryWrapper<PendingAction>()
                .eq(PendingAction::getOrderId, orderId)
                .eq(PendingAction::getStatus, "PENDING"));
        if (pending != null && pending > 0) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_EXISTS);
        }
        PendingAction action = new PendingAction();
        action.setSessionId(sessionId);
        action.setUserId(userId);
        action.setActionType("CANCEL_ORDER");
        action.setOrderId(orderId);
        action.setStatus("PENDING");
        action.setExpiresAt(LocalDateTime.now().plusMinutes(PROPOSAL_TTL_MINUTES));
        pendingActionMapper.insert(action);
        return ProposalVO.from(action);
    }

    public ProposalVO confirm(long id) {
        if (pendingActionMapper.claimForExecution(id) == 0) {
            handleClaimFailure(id);
        }
        try {
            executionService.executeClaimed(id);
        } catch (Exception ex) {
            log.error("提案 {} 副作用执行失败,标记 FAILED", id, ex);
            pendingActionMapper.markFailedIfExecuting(id);
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "提案执行失败,已标记 FAILED");
        }
        return get(id);
    }

    public ProposalVO cancel(long id) {
        if (pendingActionMapper.cancelIfPending(id) == 0) {
            handleClaimFailure(id);
        }
        return get(id);
    }

    public ProposalVO get(long id) {
        PendingAction action = pendingActionMapper.selectById(id);
        if (action == null) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_NOT_FOUND);
        }
        return ProposalVO.from(action);
    }

    /** 抢占失败的归因:404 不存在 / 410 已过期(顺带归档)/ 409 其他状态冲突。 */
    private void handleClaimFailure(long id) {
        PendingAction action = pendingActionMapper.selectById(id);
        if (action == null) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_NOT_FOUND);
        }
        if ("PENDING".equals(action.getStatus()) && action.getExpiresAt().isBefore(LocalDateTime.now())) {
            pendingActionMapper.expireIfDue(id);
            throw new BusinessException(ErrorCode.PENDING_ACTION_EXPIRED);
        }
        throw new BusinessException(ErrorCode.PENDING_ACTION_CONFLICT,
                "提案当前状态 " + action.getStatus());
    }
}
