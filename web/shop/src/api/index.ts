/**
 * Axios 请求实例与拦截器模块
 *
 * 文件作用：创建全项目唯一的 axios 实例（统一 baseURL 与超时时间），
 *      并通过请求/响应拦截器实现登录令牌自动注入、
 *      后端错误信息统一提示以及未登录（401）自动跳转登录页等通用逻辑。
 * 所属模块：前端 shop 商城项目的 API 请求层基础设施（src/api）。
 * 对外导出内容：
 *  - 默认导出：配置好的 axios 实例（供 auth/cart/orders 等业务接口模块统一使用）
 *
 * 说明：所有业务接口模块均基于本实例发起请求，因此
 *      token 注入与错误处理只需在此实现一次即可全局生效。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建统一的 axios 实例
const api = axios.create({
  // 生产化：基址由环境变量注入（.env.development/.env.production），
  // 构建产物不再依赖 dev proxy 假设
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000, // 请求超时时间：15 秒
})

// 请求拦截器：在每次发起请求前自动注入登录令牌
api.interceptors.request.use((config) => {
  // 从 localStorage 读取登录成功后持久化的 token
  const token = localStorage.getItem('shop_token')
  if (token) {
    // 按 Bearer 规范将 token 写入 Authorization 请求头，供后端鉴权
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理成功透传、失败提示与 401 未登录跳转
api.interceptors.response.use(
  // 成功响应：原样透传给调用方，由业务代码自行解析业务数据
  (res) => res,
  // 失败响应：统一弹错误提示；401 时清除本地登录态并跳回登录页
  (err) => {
    // 错误分类：网络错误（无响应）/ 权限（401/403）/ 限流（429）/ 服务端（5xx）/ 业务 4xx
    const status = err.response?.status
    let msg = '请求失败，请稍后再试'
    if (!err.response) {
      msg = '网络异常，请检查连接后重试'
    } else if (status === 401) {
      msg = '登录已过期，请重新登录'
    } else if (status === 403) {
      msg = '没有权限执行该操作'
    } else if (status === 429) {
      msg = '操作过于频繁，请稍后再试'
    } else if (status >= 500) {
      msg = '服务暂时不可用，请稍后再试'
    } else {
      msg = err.response?.data?.detail || `请求失败（${status}）`
    }
    ElMessage.error(msg)
    // 401 状态码表示 token 缺失、过期或已被吊销
    if (err.response?.status === 401) {
      // 清除本地持久化的 token，使前端恢复未登录状态
      localStorage.removeItem('shop_token')
      // 强制跳转到登录页，让用户重新登录
      window.location.href = '/login'
    }
    err.$$userMessage = msg
    // 继续向下抛出错误，供调用方按需做后续处理（如提示、回退等）
    return Promise.reject(err)
  },
)

export default api
