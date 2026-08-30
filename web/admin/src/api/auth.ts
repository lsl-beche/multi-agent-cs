/**
 * 认证模块 API
 *
 * 文件作用：封装后台管理系统「认证模块」的所有接口请求（登录、刷新令牌、获取当前用户信息、修改密码）。
 * 所属模块：认证模块（auth）。
 * 对外导出：loginApi（登录）、refreshApi（刷新访问令牌）、meApi（获取当前登录用户信息）、changePwdApi（修改密码）。
 * 说明：所有请求均基于 ./index 中创建的 axios 实例发出，统一携带 token 并做统一错误处理；
 *       接口路径以 axios 实例的 baseURL（/api）为前缀，例如登录实际请求 POST /api/auth/login。
 */

import api, { type ApiResponse } from './index'

/**
 * 登录请求参数
 * - username: 登录用户名
 * - password: 登录密码
 */
interface LoginParams { username: string; password: string }

/**
 * 登录/刷新成功后返回的令牌数据
 * - access_token: 访问令牌（有效期较短，后续请求通过请求头 Authorization: Bearer <token> 携带）
 * - refresh_token: 刷新令牌（访问令牌过期后，用它换取新的访问令牌）
 */
interface LoginData { access_token: string; refresh_token: string }

/**
 * 当前登录用户信息
 * - id: 用户 ID
 * - username: 登录用户名
 * - role: 用户角色（如 admin 管理员、staff 客服等）
 * - permissions: 用户拥有的权限标识数组，用于前端按钮/路由级权限控制
 */
interface UserData { id: number; username: string; role: string; permissions: string[] }

/**
 * 登录接口
 * @param data 登录参数（username 用户名、password 密码）
 * @returns Promise<ApiResponse<LoginData>> 登录成功时返回 access_token 与 refresh_token
 * @description 对应后端接口：POST /api/auth/login
 */
export const loginApi = (data: LoginParams) => api.post<ApiResponse<LoginData>>('/auth/login', data) // 发起登录请求，令牌由调用方存入 localStorage

/**
 * 刷新访问令牌接口（访问令牌过期后自动续期）
 * @param data 包含刷新令牌的对象（refresh_token）
 * @returns Promise<ApiResponse<LoginData>> 刷新成功时返回新的 access_token 与 refresh_token
 * @description 对应后端接口：POST /api/auth/refresh
 */
export const refreshApi = (data: { refresh_token: string }) => api.post<ApiResponse<LoginData>>('/auth/refresh', data) // 用旧刷新令牌换取新令牌

/**
 * 获取当前登录用户信息接口
 * @returns Promise<ApiResponse<UserData>> 返回当前用户的 ID、用户名、角色及权限列表
 * @description 对应后端接口：GET /api/auth/me
 */
export const meApi = () => api.get<ApiResponse<UserData>>('/auth/me') // 页面初始化时拉取用户身份与权限

/**
 * 修改密码接口
 * @param data 修改密码参数（old_password 旧密码、new_password 新密码）
 * @returns Promise 修改成功时正常 resolve（后端不返回业务数据）
 * @description 对应后端接口：PUT /api/auth/password
 */
export const changePwdApi = (data: { old_password: string; new_password: string }) => api.put('/auth/password', data) // 提交新旧密码，由后端校验旧密码
