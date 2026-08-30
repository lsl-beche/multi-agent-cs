/**
 * 支付模块 API
 *
 * 文件作用：封装后台管理系统「支付管理」的接口请求（支付记录查询、退款记录查询、退款审核处理）。
 * 所属模块：支付模块（payments）。
 * 对外导出：getPayments（分页查询支付记录）、getRefunds（分页查询退款记录）、
 *          approveRefund（同意退款）、rejectRefund（拒绝退款），以及 PaymentItem、RefundItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 支付记录条目
 * - id: 支付记录 ID
 * - payment_no: 支付单号（平台内部编号）
 * - order_id: 关联订单 ID
 * - amount: 支付金额
 * - channel: 支付渠道（如 alipay 支付宝、wechat 微信支付等）
 * - trade_no: 第三方支付平台交易号（可选，回调后回填）
 * - status: 支付状态（如 pending 待支付、success 支付成功、failed 支付失败、refunded 已退款）
 * - paid_at: 实际支付时间（可选，未支付时为空）
 * - created_at: 支付记录创建时间
 */
export interface PaymentItem { id: number; payment_no: string; order_id: number; amount: number; channel: string; trade_no?: string; status: string; paid_at?: string; created_at: string }

/**
 * 退款记录条目
 * - id: 退款记录 ID
 * - refund_no: 退款单号
 * - order_id: 关联订单 ID
 * - amount: 退款金额
 * - reason: 退款原因（可选）
 * - status: 退款状态（如 pending 待审核、approved 已同意、rejected 已拒绝、refunded 已打款）
 * - created_at: 退款申请时间
 */
export interface RefundItem { id: number; refund_no: string; order_id: number; amount: number; reason?: string; status: string; created_at: string }

/**
 * 分页查询支付记录
 * @param params 查询参数（如 page、page_size、payment_no、order_id、channel、状态、时间范围等筛选条件）
 * @returns Promise<PaginatedData<PaymentItem>> 分页的支付记录数据
 * @description 对应后端接口：GET /api/admin/payments
 */
export const getPayments = (params: Record<string, unknown>) => api.get<PaginatedData<PaymentItem>>('/admin/payments', { params }) // 携带筛选参数请求支付记录列表

/**
 * 分页查询退款记录
 * @param params 查询参数（如 page、page_size、refund_no、order_id、状态、时间范围等筛选条件）
 * @returns Promise<PaginatedData<RefundItem>> 分页的退款记录数据
 * @description 对应后端接口：GET /api/admin/payments/refunds
 */
export const getRefunds = (params: Record<string, unknown>) => api.get<PaginatedData<RefundItem>>('/admin/payments/refunds', { params }) // 携带筛选参数请求退款记录列表

/**
 * 同意退款（审核通过后执行退款）
 * @param id 退款记录 ID
 * @returns Promise 审核成功时正常 resolve
 * @description 对应后端接口：POST /api/admin/payments/refunds/{id}/approve
 */
export const approveRefund = (id: number) => api.post(`/admin/payments/refunds/${id}/approve`) // 同意后将触发实际退款流程

/**
 * 拒绝退款
 * @param id 退款记录 ID
 * @returns Promise 审核成功时正常 resolve
 * @description 对应后端接口：POST /api/admin/payments/refunds/{id}/reject
 */
export const rejectRefund = (id: number) => api.post(`/admin/payments/refunds/${id}/reject`) // 拒绝后退款申请关闭，订单恢复正常
