package com.csagent.order.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.LocalDateTime;
import lombok.Data;

/** 商品 SPU(平移子集)。 */
@Data
@TableName("products")
public class Product {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String spuCode;

    private String name;

    private String brand;

    private String status;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
