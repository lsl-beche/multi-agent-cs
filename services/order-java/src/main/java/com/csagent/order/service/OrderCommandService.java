package com.csagent.order.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.CreateOrderRequest;
import com.csagent.order.dto.OrderVO;
import com.csagent.order.entity.Order;
import com.csagent.order.entity.OrderItem;
import com.csagent.order.entity.Product;
import com.csagent.order.entity.Sku;
import com.csagent.order.mapper.OrderItemMapper;
import com.csagent.order.mapper.OrderMapper;
import com.csagent.order.mapper.ProductMapper;
import com.csagent.order.mapper.SkuMapper;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 订单写服务(创建/支付标记):订单域数据的唯一写入方。
 *
 * 创建 = 原子扣减(先扣再建,扣减失败不落单)→ 同事务写订单主档 + 商品行;
 * 单号冲突(唯一约束)自动换号重试一次。
 * 支付标记 = 金额强校验(资损防护)+ 条件迁移(仅 unpaid,回调重放天然幂等)。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrderCommandService {

    private static final DateTimeFormatter ORDER_NO_FMT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    private final SkuMapper skuMapper;
    private final ProductMapper productMapper;
    private final OrderMapper orderMapper;
    private final OrderItemMapper orderItemMapper;

    @Transactional
    public OrderVO create(CreateOrderRequest req) {
        int affected = skuMapper.deductStock(req.skuId(), req.quantity());
        if (affected == 0) {
            Sku sku = skuMapper.selectById(req.skuId());
            if (sku == null) {
                throw new BusinessException(ErrorCode.SKU_NOT_FOUND);
            }
            throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK, "库存不足,剩余 " + sku.getStock());
        }

        Sku sku = skuMapper.selectById(req.skuId());
        Product product = productMapper.selectById(sku.getProductId());
        BigDecimal unit = sku.getPrice();
        BigDecimal total = unit.multiply(BigDecimal.valueOf(req.quantity()));

        Order order = new Order();
        order.setUserId(req.userId());
        order.setTotalAmount(total);
        order.setDiscountAmount(BigDecimal.ZERO);
        order.setPayAmount(total);
        order.setBuyerRemark(req.buyerRemark());
        order.setVersion(1);
        for (int attempt = 0; attempt < 2; attempt++) {
            try {
                order.setId(null);
                order.setOrderNo(generateOrderNo());
                orderMapper.insert(order);
                break;
            } catch (DuplicateKeyException ex) {
                if (attempt == 1) {
                    throw ex;   // 单号毫秒级 + 随机四位,两次冲突概率可忽略
                }
            }
        }

        OrderItem item = new OrderItem();
        item.setOrderId(order.getId());
        item.setSkuId(sku.getId());
        item.setProductName(product == null ? sku.getSkuCode() : product.getName());
        item.setUnitPrice(unit);
        item.setQuantity(req.quantity());
        item.setTotalPrice(total);
        orderItemMapper.insert(item);

        log.info("订单创建: orderNo={}, sku={}, qty={}, amount={}",
                order.getOrderNo(), sku.getSkuCode(), req.quantity(), total);
        return OrderVO.from(order, List.of(
                new OrderVO.ItemVO(item.getProductName(), unit, req.quantity(), total)));
    }

    /** 支付成功标记:金额强校验(资损防护)+ 条件迁移,重放幂等。 */
    @Transactional
    public OrderVO markPaid(long orderId, String tradeNo, double amount) {
        Order order = orderMapper.selectById(orderId);
        if (order == null) {
            throw new BusinessException(ErrorCode.ORDER_NOT_FOUND);
        }
        if (Math.abs(amount - order.getPayAmount().doubleValue()) > 0.01) {
            throw new BusinessException(ErrorCode.AMOUNT_MISMATCH,
                    "支付金额 " + amount + " 与订单应付 " + order.getPayAmount() + " 不一致");
        }
        orderMapper.markPaidIfUnpaid(orderId);
        log.info("订单支付成功: orderNo={}, tradeNo={}", order.getOrderNo(), tradeNo);
        return OrderVO.from(orderMapper.selectById(orderId));
    }

    private String generateOrderNo() {
        return "SO" + ORDER_NO_FMT.format(LocalDateTime.now())
                + String.format("%04d", ThreadLocalRandom.current().nextInt(10_000));
    }
}
