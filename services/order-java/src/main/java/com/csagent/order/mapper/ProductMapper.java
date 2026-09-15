package com.csagent.order.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.entity.Product;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ProductMapper extends BaseMapper<Product> {
}
