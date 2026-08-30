/**
 * 营销模块 API
 *
 * 文件作用：封装后台管理系统「营销活动」的接口请求（优惠券管理、促销活动管理）。
 * 所属模块：营销模块（marketing）。
 * 对外导出：优惠券相关 getCoupons（优惠券列表）、createCoupon（创建优惠券）、deleteCoupon（删除优惠券）、grantCoupon（定向发券），
 *          促销相关 getPromotions（促销活动列表）、createPromotion（创建促销活动），以及 CouponItem、PromotionItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 优惠券条目
 * - id: 优惠券 ID
 * - name: 优惠券名称
 * - coupon_type: 优惠券类型（如 fixed 满减、percent 折扣等）
 * - threshold: 使用门槛（满多少金额可用）
 * - value: 优惠面额（满减时为金额，折扣时为折扣值）
 * - total_count: 发放总量
 * - used_count: 已使用数量
 * - user_limit: 每个用户限领数量
 * - status: 状态（如 active 生效中、disabled 已停用、expired 已过期）
 * - start_time: 生效开始时间
 * - end_time: 生效结束时间
 */
export interface CouponItem { id: number; name: string; coupon_type: string; threshold: number; value: number; total_count: number; used_count: number; user_limit: number; status: string; start_time: string; end_time: string }

/**
 * 促销活动条目
 * - id: 活动 ID
 * - name: 活动名称
 * - promo_type: 促销类型（如 discount 折扣、flash_sale 限时秒杀、group 拼团等）
 * - rules: 促销规则（结构随促销类型不同，如折扣力度、满减档位等）
 * - product_ids: 参与活动的商品 ID 列表（空数组表示全场参与）
 * - status: 活动状态（如 scheduled 未开始、ongoing 进行中、ended 已结束）
 * - start_time: 活动开始时间
 * - end_time: 活动结束时间
 */
export interface PromotionItem { id: number; name: string; promo_type: string; rules: Record<string, unknown>; product_ids: number[]; status: string; start_time: string; end_time: string }

/**
 * 分页查询优惠券列表
 * @param params 查询参数（如 page、page_size、name、status、优惠券类型等筛选条件）
 * @returns Promise<PaginatedData<CouponItem>> 分页的优惠券数据
 * @description 对应后端接口：GET /api/admin/marketing/coupons
 */
export const getCoupons = (params: Record<string, unknown>) => api.get<PaginatedData<CouponItem>>('/admin/marketing/coupons', { params }) // 携带筛选参数请求优惠券列表

/**
 * 创建优惠券
 * @param data 优惠券创建数据（名称、类型、面额、门槛、数量、有效期等）
 * @returns Promise<ApiResponse<unknown>> 创建结果，成功时返回新优惠券信息
 * @description 对应后端接口：POST /api/admin/marketing/coupons
 */
export const createCoupon = (data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>>>('/admin/marketing/coupons', data) // 提交优惠券配置到后端

/**
 * 删除优惠券
 * @param id 优惠券 ID
 * @returns Promise 删除成功时正常 resolve
 * @description 对应后端接口：DELETE /api/admin/marketing/coupons/{id}
 */
export const deleteCoupon = (id: number) => api.delete(`/admin/marketing/coupons/${id}`) // 按 ID 删除指定优惠券

/**
 * 定向发放优惠券（给指定用户发券）
 * @param id 优惠券 ID
 * @param data 发放对象（user_ids 目标用户 ID 数组）
 * @returns Promise 发放成功时正常 resolve
 * @description 对应后端接口：POST /api/admin/marketing/coupons/{id}/grant
 */
export const grantCoupon = (id: number, data: { user_ids: number[] }) => api.post<ApiResponse<{ granted: number }>>(`/admin/marketing/coupons/${id}/grant`, data) // 按用户 ID 列表批量发券

/**
 * 分页查询促销活动列表
 * @param params 查询参数（如 page、page_size、name、status、促销类型等筛选条件）
 * @returns Promise<PaginatedData<PromotionItem>> 分页的促销活动数据
 * @description 对应后端接口：GET /api/admin/marketing/promotions
 */
export const getPromotions = (params: Record<string, unknown>) => api.get<PaginatedData<PromotionItem>>('/admin/marketing/promotions', { params }) // 携带筛选参数请求活动列表

/**
 * 创建促销活动
 * @param data 促销活动创建数据（名称、类型、规则、参与商品、活动时间等）
 * @returns Promise<ApiResponse<unknown>> 创建结果，成功时返回新活动信息
 * @description 对应后端接口：POST /api/admin/marketing/promotions
 */
export const createPromotion = (data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>>>('/admin/marketing/promotions', data) // 提交活动配置到后端
