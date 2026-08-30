/**
 * 报表模块 API
 *
 * 文件作用：封装后台管理系统「数据报表」的接口请求（销售统计、客服工作台数据看板）。
 * 所属模块：报表模块（reports）。
 * 对外导出：getSalesSummary（销售统计）、getCsDashboard（客服数据看板），
 *          以及 SalesSummary（销售统计类型）、CsDashboard（客服看板类型）。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse } from './index'

/**
 * 销售统计汇总（按周期聚合）
 * - period: 统计周期（如 today、week、month，与请求参数一致）
 * - total_orders: 订单总数
 * - total_amount: 销售总额
 * - pending: 待确认订单数
 * - confirmed: 已确认订单数
 * - shipped: 已发货订单数
 * - delivered: 已送达订单数
 * - completed: 已完成订单数
 * - cancelled: 已取消订单数
 * - paid_count: 已支付订单笔数
 * - paid_amount: 已支付订单金额合计
 */
export interface SalesSummary {
  period: string; total_orders: number; total_amount: number;
  pending: number; confirmed: number; shipped: number;
  delivered: number; completed: number; cancelled: number;
  paid_count: number; paid_amount: number;
}

/**
 * 客服数据看板（按周期聚合）
 * - period: 统计周期（如 today、week、month，与请求参数一致）
 * - total_conversations: 会话总数
 * - active_conversations: 进行中的活跃会话数
 * - total_tickets: 工单总数
 * - pending_tickets: 待处理工单数
 * - handoff_rate: 转人工率（客服无法解决转交人工的比例）
 * - csat_total: 满意度评价总人次
 * - csat_avg: 满意度平均分
 */
export interface CsDashboard {
  period: string; total_conversations: number; active_conversations: number;
  total_tickets: number; pending_tickets: number;
  handoff_rate: number; csat_total: number; csat_avg: number;
}

/**
 * 获取销售统计
 * @param period 统计周期（如 today 今日、week 本周、month 本月）
 * @returns Promise<ApiResponse<SalesSummary>> 对应周期的销售汇总数据
 * @description 对应后端接口：GET /api/admin/reports/sales
 */
export const getSalesSummary = (period: string) => api.get<ApiResponse<SalesSummary>>('/admin/reports/sales', { params: { period } }) // 按周期参数请求销售统计

/**
 * 获取客服数据看板
 * @param period 统计周期（如 today 今日、week 本周、month 本月）
 * @returns Promise<ApiResponse<CsDashboard>> 对应周期的客服工作台数据
 * @description 对应后端接口：GET /api/admin/reports/cs-agent
 */
export const getCsDashboard = (period: string) => api.get<ApiResponse<CsDashboard>>('/admin/reports/cs-agent', { params: { period } }) // 按周期参数请求客服看板数据
