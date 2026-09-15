package com.csagent.order.service;

import com.csagent.order.common.ErrorCode;
import com.csagent.order.common.exception.BusinessException;
import com.csagent.order.dto.DeductResult;
import com.csagent.order.dto.InventoryVO;
import com.csagent.order.entity.Sku;
import com.csagent.order.mapper.SkuMapper;
import com.csagent.order.service.InventoryCache.CachedStock;
import com.csagent.order.service.InventoryCache.Read;
import com.csagent.order.service.InventoryCache.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 库存服务:D5-6 扣减;D10 幂等键;本轮接入缓存三防(穿透/击穿/雪崩)。
 *
 * 读路径 = 缓存优先;MISS 加互斥锁重建(double check);未抢到锁短暂等待重读,
 * 仍 MISS 直查 DB(降级,不回填防写风暴);空结果走空值缓存防穿透;
 * Redis 故障全链路 fail-open 直查 DB——缓存是加速层,不是依赖。
 * 写路径 = 成功后 Cache Aside 删除缓存,下次读回源最新值。
 *
 * 事务语义(D5-6):单条条件 UPDATE 天然原子;@Transactional 保证
 * "扣减→回读剩余量"一致性(行锁持至提交,并发串行排队)。
 */
@Service
@RequiredArgsConstructor
public class InventoryService {

    private final SkuMapper skuMapper;
    private final InventoryCache cache;

    public InventoryVO getStock(long skuId) {
        Read read = cache.read(skuId);
        if (read.result() == Result.NULL_CACHED) {
            throw notFound();
        }
        if (read.result() == Result.HIT) {
            return toVO(read.value());
        }

        // MISS → 击穿防护:互斥锁重建(double check)
        if (cache.tryLock(skuId)) {
            try {
                read = cache.read(skuId);
                if (read.result() == Result.NULL_CACHED) {
                    throw notFound();
                }
                if (read.result() == Result.HIT) {
                    return toVO(read.value());
                }
                Sku sku = skuMapper.selectById(skuId);
                if (sku == null) {
                    cache.putNull(skuId);   // 穿透防护:空值缓存
                    throw notFound();
                }
                cache.putStock(skuId, new CachedStock(sku.getSkuCode(), sku.getStock(), sku.getStatus()));
                return toVO(sku);
            } finally {
                cache.unlock(skuId);
            }
        }

        // 未抢到锁:短暂等待重读一次;仍 MISS 直查 DB(降级,不回填防写风暴)
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        read = cache.read(skuId);
        if (read.result() == Result.NULL_CACHED) {
            throw notFound();
        }
        if (read.result() == Result.HIT) {
            return toVO(read.value());
        }
        Sku sku = skuMapper.selectById(skuId);
        if (sku == null) {
            throw notFound();
        }
        return toVO(sku);
    }

    @Transactional
    public DeductResult deduct(long skuId, int quantity) {
        int affected = skuMapper.deductStock(skuId, quantity);
        if (affected == 0) {
            Sku sku = skuMapper.selectById(skuId);
            if (sku == null) {
                throw notFound();
            }
            throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK,
                    "库存不足,剩余 " + sku.getStock());
        }
        cache.evict(skuId);   // Cache Aside:写后删,下次读回源最新值
        Sku sku = skuMapper.selectById(skuId);
        return new DeductResult(sku.getSkuCode(), quantity, sku.getStock());
    }

    private InventoryVO toVO(Sku sku) {
        return new InventoryVO(sku.getSkuCode(), sku.getStock(), sku.getStatus());
    }

    private InventoryVO toVO(CachedStock cached) {
        return new InventoryVO(cached.skuCode(), cached.stock(), cached.status());
    }

    private BusinessException notFound() {
        return new BusinessException(ErrorCode.SKU_NOT_FOUND);
    }
}
