/**
 * 订单模块 API
 *
 * 文件作用：封装后台管理系统「订单管理」的接口请求（订单列表/详情查询、确认、发货、取消、完成等操作）。
 * 所属模块：订单模块（orders）。
 * 对外导出：getOrders（分页查询订单）、getOrder（订单详情）、confirmOrder（确认订单）、
 *          shipOrder（发货）、cancelOrder（取消订单）、completeOrder（完成订单），以及 OrderItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 订单条目
 * - id: 订单 ID
 * - order_no: 订单编号（对外展示用）
 * - user_id: 下单用户 ID
 * - total_amount: 订单总金额（商品原价合计）
 * - pay_amount: 实付金额（优惠/运费折算后的实际支付金额）
 * - order_status: 订单状态（如 pending 待确认、confirmed 已确认、shipped 已发货、completed 已完成、cancelled 已取消）
 * - pay_status: 支付状态（如 unpaid 未支付、paid 已支付、refunded 已退款）
 * - created_at: 下单时间
 * - paid_at: 支付时间（可选，未支付时为空）
 * - items: 订单商品明细列表（可选，详情接口返回）
 * - payments: 支付记录列表（可选，详情接口返回）
 * - logs: 订单操作日志列表（可选，详情接口返回）
 */
export interface OrderItem {
  id: number; order_no: string; user_id: number; total_amount: number;
  pay_amount: number; order_status: string; pay_status: string;
  created_at: string; paid_at?: string; items?: Record<string, unknown>[];
  payments?: Record<string, unknown>[]; logs?: Record<string, unknown>[];
}

export interface OrderLogRecord {
  id: number
  action: string
  detail?: string
  created_at: string
}

export interface OrderPaymentRecord {
  id: number
  payment_no: string
  amount: number
  channel: string
  status: string
}

export interface OrderDetailItem extends Omit<OrderItem, 'logs' | 'payments'> {
  items: Array<Record<string, string | number | undefined>>
  logs?: OrderLogRecord[]
  payments?: OrderPaymentRecord[]
}

/**
 * 分页查询订单列表
 * @param params 查询参数（如 page、page_size、order_no、user_id、订单状态、时间范围等筛选条件）
 * @returns Promise<PaginatedData<OrderItem>> 分页的订单数据
 * @description 对应后端接口：GET /api/admin/orders
 */
export const getOrders = (params: Record<string, unknown>) => api.get<PaginatedData<OrderItem>>('/admin/orders', { params }) // 携带筛选条件请求订单列表

/**
 * 查询订单详情
 * @param id 订单 ID
 * @returns Promise<ApiResponse<OrderItem>> 订单完整信息（含商品明细、支付记录、操作日志）
 * @description 对应后端接口：GET /api/admin/orders/{id}
 */
export const getOrder = (id: number) => api.get<ApiResponse<OrderDetailItem>>(`/admin/orders/${id}`) // 按 ID 拉取订单全量信息

/**
 * 确认订单（商家接单）
 * @param id 订单 ID
 * @returns Promise 确认成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/orders/{id}/confirm
 */
export const confirmOrder = (id: number) => api.put(`/admin/orders/${id}/confirm`) // 将订单从待确认流转为已确认

/**
 * 订单发货
 * @param id 订单 ID
 * @param data 发货数据（carrier 快递公司、tracking_no 快递单号，可选）
 * @returns Promise 发货成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/orders/{id}/ship
 */
export const shipOrder = (id: number, data: { carrier: string; tracking_no?: string }) => api.put(`/admin/orders/${id}/ship`, data) // 记录物流信息并推进订单状态

/**
 * 取消订单
 * @param id 订单 ID
 * @param data 可选，取消原因（reason）
 * @returns Promise 取消成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/orders/{id}/cancel
 */
export const cancelOrder = (id: number, data?: { reason?: string }) => api.put(`/admin/orders/${id}/cancel`, data || {}) // 未传原因时兜底为空对象，避免请求体为 null

/**
 * 完成订单（确认收货/交易完结）
 * @param id 订单 ID
 * @returns Promise 完成成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/orders/{id}/complete
 */
export const completeOrder = (id: number) => api.put(`/admin/orders/${id}/complete`) // 将订单流转为已完成状态
