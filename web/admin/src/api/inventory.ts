/**
 * 库存模块 API
 *
 * 文件作用：封装后台管理系统「库存管理」的接口请求（库存列表查询、库存调整、库存变动流水查询）。
 * 所属模块：库存模块（inventory）。
 * 对外导出：getInventory（分页查询库存列表）、adjustInventory（库存调整）、getInventoryLogs（查询库存流水），
 *          以及 InventoryItem（库存条目类型）、InventoryLog（库存变动流水类型）。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 库存条目（单个 SKU 的库存快照）
 * - id: 库存记录 ID
 * - sku_id: 关联的 SKU ID
 * - sku_code: SKU 编码（可选，列表接口可能不返回）
 * - product_name: 所属商品名称（可选，联表查询时返回）
 * - warehouse_id: 仓库 ID（0 或负值通常代表总仓/共享库存）
 * - quantity: 当前可用库存数量
 * - locked_quantity: 已锁定数量（如已下单未支付的占用量）
 * - safety_stock: 安全库存阈值，低于该值应触发补货提醒
 * - updated_at: 最近更新时间
 */
export interface InventoryItem { id: number; sku_id: number; sku_code?: string; product_name?: string; warehouse_id: number; quantity: number; locked_quantity: number; safety_stock: number; updated_at: string }

/**
 * 库存变动流水（每次入库/出库/调整对应一条记录）
 * - id: 流水 ID
 * - sku_id: 关联的 SKU ID
 * - change_qty: 变动数量（正数表示入库/增加，负数表示出库/减少）
 * - before_qty: 变动前库存数量
 * - after_qty: 变动后库存数量
 * - reason: 变动原因（如 采购入库、订单发货、人工调整 等）
 * - created_at: 变动发生时间
 */
export interface InventoryLog { id: number; sku_id: number; change_qty: number; before_qty: number; after_qty: number; reason: string; created_at: string }

/**
 * 分页查询库存列表
 * @param params 查询参数（如 page、page_size、sku_code、product_name、warehouse_id 等筛选条件）
 * @returns Promise<PaginatedData<InventoryItem>> 分页的库存条目数据
 * @description 对应后端接口：GET /api/admin/inventory
 */
export const getInventory = (params: any) => api.get<PaginatedData<InventoryItem>>('/admin/inventory', { params }) // 携带查询参数请求库存列表

/**
 * 库存调整（人工盘点修正 / 手动出入库）
 * @param data 调整数据（sku_id 目标 SKU、change_qty 变动数量可正可负、reason 调整原因）
 * @returns Promise<ApiResponse<any>> 调整结果，成功时 data 通常为调整后的库存信息
 * @description 对应后端接口：POST /api/admin/inventory/adjust
 */
export const adjustInventory = (data: { sku_id: number; change_qty: number; reason: string }) => api.post<ApiResponse<any>>('/admin/inventory/adjust', data) // 变动数量正数为入库、负数为出库

/**
 * 分页查询库存变动流水
 * @param params 查询参数（如 page、page_size、sku_id、起止时间等筛选条件）
 * @returns Promise<PaginatedData<InventoryLog>> 分页的库存流水数据
 * @description 对应后端接口：GET /api/admin/inventory/logs
 */
export const getInventoryLogs = (params: any) => api.get<PaginatedData<InventoryLog>>('/admin/inventory/logs', { params }) // 用于库存追溯与对账
