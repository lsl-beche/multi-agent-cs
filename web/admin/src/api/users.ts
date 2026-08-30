/**
 * 用户管理模块 API
 *
 * 文件作用：封装后台管理系统「用户管理」的接口请求（用户列表、新增/编辑用户、封禁用户、查询收货地址）。
 * 所属模块：用户模块（users）。
 * 对外导出：getUsers（分页查询用户）、createUser（新增用户）、updateUser（编辑用户）、
 *          banUser（封禁/解封用户）、getAddresses（查询用户收货地址），以及 UserItem、AddressItem 类型。
 * 说明：所有请求基于 ./index 的 axios 实例，实际路径带 /api 前缀。
 */

import api, { type ApiResponse, type PaginatedData } from './index'

/**
 * 用户条目
 * - id: 用户 ID
 * - username: 用户名
 * - email: 邮箱（可选）
 * - phone: 手机号（可选）
 * - status: 用户状态（如 active 正常、banned 已封禁）
 * - role: 用户角色（如 user 普通用户、vip 会员等）
 * - created_at: 注册时间
 */
export interface UserItem { id: number; username: string; email?: string; phone?: string; status: string; role: string; created_at: string }

/**
 * 收货地址条目
 * - id: 地址 ID
 * - receiver: 收货人姓名
 * - phone: 收货人电话
 * - province: 省份
 * - city: 城市
 * - district: 区/县
 * - detail: 详细地址
 * - is_default: 是否为默认收货地址
 */
export interface AddressItem { id: number; receiver: string; phone: string; province: string; city: string; district: string; detail: string; is_default: boolean }

/**
 * 分页查询用户列表
 * @param params 查询参数（如 page、page_size、username、phone、status、role 等筛选条件）
 * @returns Promise<PaginatedData<UserItem>> 分页的用户数据
 * @description 对应后端接口：GET /api/admin/users
 */
export const getUsers = (params: any) => api.get<PaginatedData<UserItem>>('/admin/users', { params }) // 携带筛选参数请求用户列表

/**
 * 新增用户（后台手动创建账号）
 * @param data 用户创建数据（username 用户名、password 密码必填；email、phone 可选；role 角色）
 * @returns Promise<ApiResponse<any>> 创建结果，成功时返回新用户信息
 * @description 对应后端接口：POST /api/admin/users
 */
export const createUser = (data: { username: string; password: string; email?: string; phone?: string; role: string }) => api.post<ApiResponse<any>>('/admin/users', data) // 提交新账号信息到后端

/**
 * 编辑用户信息
 * @param id 用户 ID
 * @param data 用户更新数据（如邮箱、手机号、角色等，仅传需要修改的字段）
 * @returns Promise<ApiResponse<any>> 更新结果，成功时返回更新后的用户信息
 * @description 对应后端接口：PUT /api/admin/users/{id}
 */
export const updateUser = (id: number, data: any) => api.put<ApiResponse<any>>(`/admin/users/${id}`, data) // 按 ID 提交用户信息修改

/**
 * 封禁/解封用户（后端根据用户当前状态自动切换）
 * @param id 用户 ID
 * @returns Promise 操作成功时正常 resolve
 * @description 对应后端接口：PUT /api/admin/users/{id}/ban
 */
export const banUser = (id: number) => api.put(`/admin/users/${id}/ban`) // 封禁后该用户无法登录/下单

/**
 * 查询用户的收货地址列表
 * @param userId 用户 ID
 * @returns Promise<ApiResponse<AddressItem[]>> 该用户的地址数组
 * @description 对应后端接口：GET /api/admin/users/{userId}/addresses
 */
export const getAddresses = (userId: number) => api.get<ApiResponse<AddressItem[]>>(`/admin/users/${userId}/addresses`) // 用于查看/核对用户地址信息
