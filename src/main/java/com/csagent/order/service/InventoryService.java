package com.csagent.order.service;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.DeductResult;
import com.csagent.order.dto.InventoryVO;
import com.csagent.order.entity.Sku;
import com.csagent.order.mapper.SkuMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 库存服务:D5-6 扣减;幂等键拦截在 D10 统一接入。
 *
 * 设计要点:
 * - 单条条件 UPDATE 天然原子,不依赖 @Transactional 保证扣减本身;
 * - 事务的作用是"扣减→回读剩余量"的一致性:UPDATE 持有的行锁到提交才释放,
 *   并发请求在行上串行排队,读到的 remaining 不会是别的请求扣到一半的值;
 * - affected=0 时二次查询区分"不存在"与"不足",给调用方可行动的错误。
 */
@Service
@RequiredArgsConstructor
public class InventoryService {

    private final SkuMapper skuMapper;

    @Transactional
    public DeductResult deduct(long skuId, int quantity) {
        int affected = skuMapper.deductStock(skuId, quantity);
        if (affected == 1) {
            Sku sku = skuMapper.selectById(skuId);
            return new DeductResult(sku.getSkuCode(), quantity, sku.getStock());
        }
        Sku sku = skuMapper.selectById(skuId);
        if (sku == null) {
            throw new BusinessException(ErrorCode.SKU_NOT_FOUND);
        }
        throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK,
                "库存不足,剩余 " + sku.getStock());
    }

    public InventoryVO getStock(long skuId) {
        Sku sku = skuMapper.selectById(skuId);
        if (sku == null) {
            throw new BusinessException(ErrorCode.SKU_NOT_FOUND);
        }
        return new InventoryVO(sku.getSkuCode(), sku.getStock(), sku.getStatus());
    }
}
