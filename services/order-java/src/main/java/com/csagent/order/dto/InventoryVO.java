package com.csagent.order.dto;

/** 库存查询视图。 */
public record InventoryVO(String skuCode, int stock, String status) {
}
