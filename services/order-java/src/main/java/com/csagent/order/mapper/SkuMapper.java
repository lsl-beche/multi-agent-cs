package com.csagent.order.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.entity.Sku;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface SkuMapper extends BaseMapper<Sku> {

    /**
     * 原子扣减:条件 UPDATE 把"查库存→判够不够→减库存"压缩成一条语句,
     * 由 InnoDB 行锁保证串行,受影响行数即扣减结果:
     *   1 = 扣减成功;0 = 库存不足或 SKU 不存在/停用。
     * 同时自增 version(与 CSagent 的乐观锁列语义保持一致)。
     */
    @Update("UPDATE skus SET stock = stock - #{quantity}, version = version + 1 "
            + "WHERE id = #{skuId} AND stock >= #{quantity} AND status = 'active'")
    int deductStock(@Param("skuId") long skuId, @Param("quantity") int quantity);
}
