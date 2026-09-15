package com.csagent.order.controller;

import com.csagent.order.common.ApiResponse;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.entity.Order;
import com.csagent.order.entity.PendingAction;
import com.csagent.order.mapper.OrderMapper;
import com.csagent.order.mapper.PendingActionMapper;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 对拍演示接口(仅 debug,生产必须关闭 app.debug-enabled):
 * - confirm-legacy:逐字复刻 Python confirm_action_node 的"读→判→写(sleep 放大窗口)"缺陷,
 *   用于证明并发下副作用会重复执行;
 * - side-effect:读订单 version(初始 1),version-1 = 副作用实际执行次数。
 */
@RestController
@RequestMapping("/api/debug")
@RequiredArgsConstructor
public class DebugController {

    private final PendingActionMapper pendingActionMapper;
    private final OrderMapper orderMapper;

    @Value("${app.debug-enabled:false}")
    private boolean debugEnabled;

    @PostMapping("/pending-actions/{id}/confirm-legacy")
    public ApiResponse<String> confirmLegacy(@PathVariable long id) throws InterruptedException {
        requireDebug();
        PendingAction action = pendingActionMapper.selectById(id);
        if (action == null) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_NOT_FOUND);
        }
        Thread.sleep(80);   // 人为放大竞态窗口,模拟 Python 侧"确认判断→Redis 写回"间的多次往返
        if (!"PENDING".equals(action.getStatus())) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_CONFLICT,
                    "提案当前状态 " + action.getStatus());
        }
        // 缺陷复刻:终态写入与副作用都不带状态条件,读过期即写
        pendingActionMapper.markDoneUnconditional(id);
        orderMapper.incrementVersion(action.getOrderId());
        return ApiResponse.ok("legacy done");
    }

    @GetMapping("/side-effect")
    public ApiResponse<Map<String, Object>> sideEffect(@RequestParam long orderId,
                                                       @RequestParam long actionId) {
        requireDebug();
        Order order = orderMapper.selectById(orderId);
        PendingAction action = pendingActionMapper.selectById(actionId);
        if (order == null || action == null) {
            throw new BusinessException(ErrorCode.PENDING_ACTION_NOT_FOUND);
        }
        return ApiResponse.ok(Map.of(
                "orderVersion", order.getVersion(),
                "executions", order.getVersion() - 1,
                "orderStatus", order.getOrderStatus(),
                "actionStatus", action.getStatus()));
    }

    private void requireDebug() {
        if (!debugEnabled) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "debug 接口未开启");
        }
    }
}
