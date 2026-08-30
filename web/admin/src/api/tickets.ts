/**
 * 客服工单模块 API
 *
 * 文件作用：封装后台管理系统「客服工单」的接口请求（工单列表查询、工单详情、认领工单、回复工单）。
 * 所属模块：客服工单模块（tickets）。
 * 对外导出：getTickets（分页查询工单）、getTicketDetail（工单详情）、claimTicket（认领工单）、
 *          replyTicket（回复工单），以及 TicketItem、TicketDetail 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse } from './index'

/**
 * 客服工单条目
 */
export interface TicketItem {
  ticket_id: string // 工单 ID（字符串，客服端唯一标识）
  session_id: string // 关联的客服会话 ID（工单由会话转来）
  user_id: string // 发起工单的用户 ID
  category: string // 工单分类（如 售后、物流、咨询 等）
  description: string // 问题描述
  status: string // 工单状态（如 open 待认领、claimed 已认领、closed 已关闭）
  handler: string // 处理客服（未认领时为空或占位值）
  created_at: string // 工单创建时间
}

/**
 * 工单详情
 */
export interface TicketDetail {
  ticket: TicketItem // 工单基本信息
  messages: Array<{ role: string; content: string; time: string }> // 会话消息记录（role 消息角色、content 消息内容、time 发送时间）
  user_online: boolean // 用户当前是否在线（在线可即时回复）
}

/**
 * 查询工单列表（可按状态筛选）
 * @param status 工单状态筛选（如 open 待认领、claimed 已认领、closed 已关闭；不传则查询全部，可选）
 * @returns Promise<ApiResponse<{ tickets: TicketItem[]; total: number }>> 工单数组及总数
 * @description 对应后端接口：GET /api/ticket/admin/list
 */
export const getTickets = (status?: string) =>
  // 状态为空时后端默认返回全部工单
  api.get<ApiResponse<{ tickets: TicketItem[]; total: number }>>('/ticket/admin/list', { params: { status } })

/**
 * 查询工单详情（含会话消息记录）
 * @param ticketId 工单 ID
 * @returns Promise<ApiResponse<TicketDetail>> 工单信息、消息记录及用户在线状态
 * @description 对应后端接口：GET /api/ticket/admin/{ticketId}/detail
 */
export const getTicketDetail = (ticketId: string) =>
  api.get<ApiResponse<TicketDetail>>(`/ticket/admin/${ticketId}/detail`) // 按工单 ID 拉取完整上下文

/**
 * 认领工单（客服接管该工单）
 * @param ticketId 工单 ID
 * @returns Promise<ApiResponse<TicketItem>> 认领成功后返回更新后的工单信息（handler 变为当前客服）
 * @description 对应后端接口：POST /api/ticket/admin/{ticketId}/claim
 */
export const claimTicket = (ticketId: string) =>
  api.post<ApiResponse<TicketItem>>(`/ticket/admin/${ticketId}/claim`) // 认领后工单归当前客服处理

/**
 * 回复工单（客服发送消息给用户）
 * @param ticketId 工单 ID
 * @param content 回复内容
 * @param handler 处理客服标识（记录是谁回复的）
 * @returns Promise<ApiResponse<TicketItem>> 回复成功后返回更新后的工单信息
 * @description 对应后端接口：POST /api/ticket/admin/{ticketId}/reply（参数通过 query 传递）
 */
export const replyTicket = (ticketId: string, content: string, handler: string) =>
  api.post<ApiResponse<TicketItem>>('/ticket/admin/' + ticketId + '/reply', null, {
    params: { content, handler }, // 回复内容与客服标识以 URL 查询参数形式提交
  })
