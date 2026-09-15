package com.csagent.order.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.entity.Order;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface OrderMapper extends BaseMapper<Order> {

    /** 取消副作用:条件化使重复执行天然幂等(已取消则 0 行,不再 +version)。 */
    @Update("UPDATE orders SET order_status = 'cancelled', cancelled_at = NOW(), version = version + 1 "
            + "WHERE id = #{orderId} AND order_status <> 'cancelled'")
    int cancelIfNotCancelled(@Param("orderId") long orderId);

    /** 对拍专用:无条件 +version,把"副作用被执行了几次"变成可观测计数。生产代码禁止使用。 */
    @Update("UPDATE orders SET version = version + 1 WHERE id = #{orderId}")
    int incrementVersion(@Param("orderId") long orderId);
}
