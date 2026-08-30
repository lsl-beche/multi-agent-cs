/**
 * 评价管理模块 API
 *
 * 文件作用：封装后台管理系统「商品评价」的接口请求（评价列表查询、审核通过/拒绝、商家回复）。
 * 所属模块：评价模块（reviews）。
 * 对外导出：getReviews（分页查询评价）、approveReview（审核通过）、rejectReview（审核拒绝）、
 *          replyReview（回复评价），以及 ReviewItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 商品评价条目
 * - id: 评价 ID
 * - product_id: 被评价商品 ID
 * - order_id: 关联订单 ID（评价一般由已完成的订单产生）
 * - rating: 评分（如 1~5 星）
 * - content: 评价文字内容（可选，纯图片评价可能为空）
 * - images: 评价图片 URL 列表（可选）
 * - is_anonymous: 是否匿名评价
 * - status: 评价状态（如 pending 待审核、approved 已通过、rejected 已拒绝）
 * - reply: 商家回复内容（可选，未回复时为空）
 * - created_at: 评价提交时间
 */
export interface ReviewItem { id: number; product_id: number; order_id: number; rating: number; content?: string; images?: string[]; is_anonymous: boolean; status: string; reply?: string; created_at: string }

/**
 * 分页查询评价列表
 * @param params 查询参数（如 page、page_size、product_id、rating、status、时间范围等筛选条件）
 * @returns Promise<PaginatedData<ReviewItem>> 分页的评价数据
 * @description 对应后端接口：GET /api/admin/reviews
 */
export const getReviews = (params: Record<string, unknown>) => api.get<PaginatedData<ReviewItem>>('/admin/reviews', { params }) // 携带筛选参数请求评价列表

/**
 * 审核通过评价（评价内容合规后放行展示）
 * @param id 评价 ID
 * @returns Promise 审核成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/reviews/{id}/approve
 */
export const approveReview = (id: number) => api.put(`/admin/reviews/${id}/approve`) // 通过后评价将对外展示

/**
 * 审核拒绝评价（违规内容驳回）
 * @param id 评价 ID
 * @returns Promise 审核成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/reviews/{id}/reject
 */
export const rejectReview = (id: number) => api.put(`/admin/reviews/${id}/reject`) // 拒绝后评价不对外展示

/**
 * 商家回复评价
 * @param id 评价 ID
 * @param data 回复数据（reply 回复内容）
 * @returns Promise 回复成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/reviews/{id}/reply
 */
export const replyReview = (id: number, data: { reply: string }) => api.put(`/admin/reviews/${id}/reply`, data) // 提交商家回复内容
