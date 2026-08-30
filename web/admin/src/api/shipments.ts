/**
 * 物流发货模块 API
 *
 * 文件作用：封装后台管理系统「物流发货」的接口请求（发货单列表查询、更新物流追踪信息）。
 * 所属模块：物流发货模块（shipments）。
 * 对外导出：getShipments（分页查询发货单）、updateTracking（更新物流单号），以及 ShipmentItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 发货单条目
 * - id: 发货单 ID
 * - shipment_no: 发货单号（平台内部编号）
 * - order_id: 关联订单 ID
 * - carrier: 快递公司（如 顺丰、圆通 等）
 * - tracking_no: 快递单号（可选，未发货/未录入时为空）
 * - status: 发货状态（如 pending 待发货、shipped 已发货、delivered 已签收）
 * - receiver: 收货人姓名
 * - receiver_phone: 收货人电话
 * - address: 收货地址（省市区 + 详细地址）
 * - shipped_at: 发货时间（可选，未发货时为空）
 * - created_at: 发货单创建时间
 */
export interface ShipmentItem { id: number; shipment_no: string; order_id: number; carrier: string; tracking_no?: string; status: string; receiver: string; receiver_phone: string; address: string; shipped_at?: string; created_at: string }

/**
 * 分页查询发货单列表
 * @param params 查询参数（如 page、page_size、shipment_no、order_id、status、快递公司等筛选条件）
 * @returns Promise<PaginatedData<ShipmentItem>> 分页的发货单数据
 * @description 对应后端接口：GET /api/admin/shipments
 */
export const getShipments = (params: Record<string, unknown>) => api.get<PaginatedData<ShipmentItem>>('/admin/shipments', { params }) // 携带筛选参数请求发货单列表

/**
 * 更新物流追踪信息（补录/修改快递单号）
 * @param id 发货单 ID
 * @param data 更新数据（tracking_no 快递单号必填、carrier 快递公司可选）
 * @returns Promise 更新成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/shipments/{id}/track
 */
export const updateTracking = (id: number, data: { tracking_no: string; carrier?: string }) => api.put(`/admin/shipments/${id}/track`, data) // 用于线下发货后回填物流信息
