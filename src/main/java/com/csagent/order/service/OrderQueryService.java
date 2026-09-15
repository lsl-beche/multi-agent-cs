package com.csagent.order.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.csagent.order.common.PageResult;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.entity.Order;
import com.csagent.order.mapper.OrderMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * 订单查询:D3-4 只读;取消/确认等写链路在 D8-10 落地。
 */
@Service
@RequiredArgsConstructor
public class OrderQueryService {

    private final OrderMapper orderMapper;

    public OrderVO getById(long id) {
        Order order = orderMapper.selectById(id);
        if (order == null) {
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND);
        }
        return OrderVO.from(order);
    }

    public PageResult<OrderVO> page(long userId, String orderStatus, String payStatus, int page, int size) {
        LambdaQueryWrapper<Order> qw = new LambdaQueryWrapper<Order>()
                .eq(Order::getUserId, userId)
                .eq(StringUtils.hasText(orderStatus), Order::getOrderStatus, orderStatus)
                .eq(StringUtils.hasText(payStatus), Order::getPayStatus, payStatus)
                .orderByDesc(Order::getCreatedAt);

        Page<Order> result = orderMapper.selectPage(new Page<>(page, size), qw);
        return new PageResult<>(result.getTotal(), result.getCurrent(), (int) result.getSize(),
                result.getRecords().stream().map(OrderVO::from).toList());
    }
}
