/**
 * HTTP 请求封装模块（axios 实例）
 *
 * 文件作用：创建后台管理系统全局唯一的 axios 实例，统一配置接口基础路径与超时时间，
 *          并通过请求/响应拦截器实现「自动携带 token」「统一错误提示」「token 过期自动刷新」。
 * 所属模块：基础设施模块（HTTP 请求层），是所有业务 API 文件（auth、orders、users 等）的共同依赖。
 * 对外导出：api（axios 实例，供各业务 API 模块复用）、ApiResponse（通用响应类型）、PaginatedData（分页响应类型）。
 * 说明：baseURL 为 /api，所有请求实际发往后端 /api 前缀下的接口；
 *       响应拦截器直接返回 res.data，因此业务侧拿到的是后端响应体（{ code, data, message }）而非完整 axios 响应。
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 创建 axios 实例
 * baseURL: 统一接口前缀，所有请求自动拼接为 /api/xxx
 * timeout: 请求超时时间（毫秒），超过 15 秒未响应则判定失败
 */
const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

/**
 * 请求拦截器：每次请求发出前自动携带身份令牌
 * 从 localStorage 读取访问令牌，若存在则写入请求头 Authorization: Bearer <token>，供后端鉴权使用
 */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token') // 读取本地保存的访问令牌
  if (token) config.headers.Authorization = `Bearer ${token}` // 令牌存在则注入请求头
  return config
})

/**
 * 响应拦截器：统一错误处理 + token 过期自动刷新
 *
 * 处理策略：
 * 1. 成功响应直接透传响应体数据（res.data）；
 * 2. 遇到 401（未授权/token 过期）时，尝试用 refresh_token 刷新令牌并重放原请求；
 * 3. 刷新失败或无刷新令牌时，清空本地登录态并跳转登录页；
 * 4. 其余错误统一提取错误信息并通过 Element Plus 消息组件提示。
 */

// 是否正在执行令牌刷新（防止并发请求重复触发刷新）
let isRefreshing = false
// 等待队列：令牌刷新期间到达的请求先挂起，刷新成功后用新令牌统一重放
let pendingRequests: Array<(token: string) => void> = []

api.interceptors.response.use(
  // 成功时直接返回响应体（后端的 { code, data, message } 结构），业务层无需再取 res.data
  (res) => res.data,
  async (err) => {
    const original = err.config // 取出触发错误的原始请求配置，用于后续重放
    // 仅处理 401 且该请求未重试过的情况，避免刷新失败后陷入死循环
    if (err.response?.status === 401 && !original._retry) {
      // 已有刷新流程在进行中：将当前请求挂起，等待新令牌产生后再重放
      if (isRefreshing) {
        return new Promise((resolve) => {
          pendingRequests.push((token: string) => {
            original.headers.Authorization = `Bearer ${token}` // 用刷新后的新令牌重写请求头
            resolve(api(original)) // 重放原请求
          })
        })
      }

      original._retry = true // 标记该请求已重试过
      isRefreshing = true // 进入刷新状态，后续 401 请求统一排队等待

      const refreshToken = localStorage.getItem('refresh_token') // 读取本地保存的刷新令牌
      if (!refreshToken) {
        // 没有刷新令牌（登录态已被清空），直接回登录页
        localStorage.clear() // 清空本地登录数据
        window.location.href = '/login' // 跳转登录页
        return Promise.reject(err)
      }

      try {
        // 用刷新令牌换取新令牌；此处使用原生 axios 调用，避免再次进入本拦截器造成递归
        const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
        const newToken = res.data.data.access_token // 从响应中取出新的访问令牌
        localStorage.setItem('token', newToken) // 更新本地访问令牌
        original.headers.Authorization = `Bearer ${newToken}` // 原请求改用新令牌
        pendingRequests.forEach((cb) => cb(newToken)) // 通知所有排队请求使用新令牌重放
        pendingRequests = [] // 清空等待队列
        return api(original) // 重放当前请求
      } catch {
        // 刷新令牌也已失效：清空登录态并跳转登录页
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(err)
      } finally {
        isRefreshing = false // 无论刷新成败，均解除刷新锁
      }
    }

    // 非 401 错误或重试后仍失败：优先展示后端 detail 信息，其次展示错误消息，兜底为“请求失败”
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg) // 通过 Element Plus 全局消息组件提示用户
    return Promise.reject(err)
  }
)

// 导出 axios 实例，供所有业务 API 模块复用
export default api

/**
 * 后端统一响应结构类型
 * - code: 业务状态码（约定 0 或 200 表示成功，具体以后端约定为准）
 * - data: 实际业务数据（通过泛型 T 指定具体类型）
 * - message: 可选的提示信息（错误时通常携带错误描述）
 */
export type ApiResponse<T = any> = { code: number; data: T; message?: string }

/**
 * 分页数据响应类型（继承 ApiResponse，data 为数组）
 * - total: 总记录数
 * - page: 当前页码
 * - page_size: 每页记录数
 */
export type PaginatedData<T = any> = ApiResponse<T[]> & { total: number; page: number; page_size: number }
