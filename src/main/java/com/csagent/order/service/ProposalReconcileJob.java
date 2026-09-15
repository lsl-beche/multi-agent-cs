package com.csagent.order.service;

import com.csagent.order.mapper.PendingActionMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 提案对账任务(30s 一轮):
 * 1. 归档过期 PENDING → EXPIRED;
 * 2. 回收卡死的 EXECUTING(>60s)→ PENDING 重抢。
 * 副作用条件化保证回收重放安全(见 ProposalExecutionService)。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ProposalReconcileJob {

    private final PendingActionMapper pendingActionMapper;

    @Scheduled(fixedDelay = 30_000)
    public void reconcile() {
        int expired = pendingActionMapper.expireDuePending();
        int requeued = pendingActionMapper.requeueStuck();
        if (expired > 0 || requeued > 0) {
            log.info("提案对账:过期归档 {},卡死回收 {}", expired, requeued);
        }
    }
}
