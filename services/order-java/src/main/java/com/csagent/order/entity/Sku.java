package com.csagent.order.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import lombok.Data;

/**
 * SKU(含单仓库存)。CSagent 的 inventory 独立表在此合并为 stock/version 列(见 README D1-2)。
 */
@Data
@TableName("skus")
public class Sku {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String skuCode;

    private Long productId;

    private String specInfo;

    private BigDecimal price;

    private Integer stock;

    private Integer version;

    private String status;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
