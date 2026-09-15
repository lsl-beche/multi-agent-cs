package com.csagent.order.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.csagent.order.common.PageResult;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.entity.Order;
import com.csagent.order.entity.OrderItem;
import com.csagent.order.mapper.OrderItemMapper;
import com.csagent.order.mapper.OrderMapper;
import lombok.RequiredArgsConstructor;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * 订单查询:D3-4 只读;取消/确认等写链路在 D8-10 落地。
 */
@Service
@RequiredArgsConstructor
public class OrderQueryService {

    private final OrderMapper orderMapper;
    private final OrderItemMapper orderItemMapper;

    public OrderVO getById(long id) {
        Order order = orderMapper.selectById(id);
        if (order == null) {
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND);
        }
        List<OrderVO.ItemVO> items = orderItemMapper.selectList(
                        new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, id))
                .stream()
                .map(i -> new OrderVO.ItemVO(i.getProductName(), i.getUnitPrice(),
                        i.getQuantity(), i.getTotalPrice()))
                .toList();
        return OrderVO.from(order, items);
    }

    /** 按业务单号查询:供 Python 智能层(单号字符串)换算本服务数字主键。 */
    public long getIdByOrderNo(String orderNo) {
        Order order = orderMapper.selectOne(
                new LambdaQueryWrapper<Order>().eq(Order::getOrderNo, orderNo));
        if (order == null) {
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND);
        }
        return order.getId();
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
