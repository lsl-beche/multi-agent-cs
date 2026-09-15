package com.csagent.order.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.entity.OrderItem;
import com.csagent.order.entity.PendingAction;
import com.csagent.order.mapper.OrderItemMapper;
import com.csagent.order.mapper.OrderMapper;
import com.csagent.order.mapper.PendingActionMapper;
import com.csagent.order.mapper.SkuMapper;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 执行服务:持有执行权的提案,在一个事务里完成"副作用 + 标记 DONE"。
 * 单独成 Bean 的原因:Spring @Transactional 经代理生效,同类自调用会失效(经典坑)。
 *
 * 副作用本身条件化(仅非 cancelled 才更新):即使 EXECUTING 超时被回收重抢、
 * 副作用重放,也不会重复变更——这是崩溃恢复安全的前提。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ProposalExecutionService {

    private final PendingActionMapper pendingActionMapper;
    private final OrderMapper orderMapper;
    private final OrderItemMapper orderItemMapper;
    private final SkuMapper skuMapper;

    @Transactional
    public void executeClaimed(long actionId) {
        PendingAction action = pendingActionMapper.selectById(actionId);
        if (action == null) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_NOT_FOUND);
        }
        if (orderMapper.selectById(action.getOrderId()) == null) {
            pendingActionMapper.markFailedIfExecuting(actionId);
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND, "提案指向的订单不存在,已标 FAILED");
        }
        int cancelled = orderMapper.cancelIfNotCancelled(action.getOrderId());
        if (cancelled == 1) {
            // 同事务回补库存:取消生效才回补,重放天然幂等
            List<OrderItem> items = orderItemMapper.selectList(
                    new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, action.getOrderId()));
            for (OrderItem item : items) {
                skuMapper.restoreStock(item.getSkuId(), item.getQuantity());
            }
        }
        int marked = pendingActionMapper.markDoneIfExecuting(actionId);
        if (marked == 0) {
            // 抢占被超时回收抢走(副作用条件化,重放无害),此处仅告警
            log.warn("提案 {} 标记 DONE 时状态已非 EXECUTING(被回收?),副作用已条件化执行", actionId);
        }
    }
}
