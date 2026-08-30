/**
 * ============================================================
 * 模块说明：认证状态管理（stores/auth.ts）
 *
 * 职责：
 *   - 管理登录态相关的全局状态：访问令牌（token）、刷新令牌（refresh_token）、
 *     当前用户信息（user）
 *   - 提供登录、登出、获取当前用户、刷新令牌等异步动作
 *   - token 同时持久化到 localStorage，刷新页面后仍可保持登录态；
 *     路由守卫与 axios 拦截器都依赖这里的 token 做鉴权
 *
 * 使用方式（在任意组件中）：
 *   const auth = useAuthStore()
 *   await auth.login(username, password)
 *   auth.logout() / auth.fetchMe() / auth.doRefresh()
 * ============================================================
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminTokenStorage, type UserProfile } from '@shared'
import { loginApi, refreshApi, meApi } from '@/api/auth'

/**
 * 用户信息数据结构（对应后端 /auth/me 接口返回）
 * - id:          用户 ID
 * - username:    用户名
 * - role:        角色（super_admin / admin / operator / viewer 等）
 * - permissions: 权限点列表（用于细粒度权限控制）
 */
type UserInfo = UserProfile

/**
 * 认证 Store（setup 语法风格）
 * 通过 defineStore 定义，'auth' 为全局唯一标识
 */
export const useAuthStore = defineStore('auth', () => {
  // 访问令牌：调用受保护接口时使用，从 localStorage 初始化以保持刷新后的登录态
  const token = ref<string>(adminTokenStorage.accessToken)
  // 刷新令牌：访问令牌过期后用于换取新令牌
  const refreshToken = ref<string>(adminTokenStorage.refreshToken)
  // 当前登录用户信息（未登录时为 null）
  const user = ref<UserInfo | null>(null)

  /**
   * 是否已登录（计算属性）
   * @returns {boolean} 存在 token 即视为已登录
   */
  const isLoggedIn = computed(() => !!token.value)

  /**
   * 登录动作
   * 调用登录接口换取令牌，持久化到 localStorage 后拉取用户信息
   * @param username 用户名
   * @param password 密码
   * @throws 登录失败时向上抛出错误，由调用方（登录页）处理提示
   */
  async function login(username: string, password: string) {
    // 调用后端登录接口，换取访问令牌与刷新令牌
    const res = await loginApi({ username, password })
    // 写入内存中的访问令牌状态
    token.value = res.data.access_token
    // 写入内存中的刷新令牌状态
    refreshToken.value = res.data.refresh_token
    // 通过统一 TokenStorage 持久化（默认 sessionStorage）
    adminTokenStorage.setTokens(res.data.access_token, res.data.refresh_token)
    // 登录成功后拉取当前用户信息并存入 user
    await fetchMe()
  }

  /**
   * 获取当前登录用户信息
   * 成功则写入 user；失败（如 token 失效）则自动登出，清理残留的无效登录态
   */
  async function fetchMe() {
    try {
      // 调用 /auth/me 接口获取当前用户信息
      const res = await meApi()
      user.value = res.data
      localStorage.setItem('permissions', JSON.stringify(res.data.permissions || []))
    } catch {
      // token 失效或网络异常：执行登出
      logout()
    }
  }

  /**
   * 刷新访问令牌
   * 使用刷新令牌换取新的访问令牌；刷新失败（如刷新令牌也已过期）则登出
   */
  async function doRefresh() {
    try {
      // 携带刷新令牌调用刷新接口
      const res = await refreshApi({ refresh_token: refreshToken.value })
      // 更新内存中的访问令牌
      token.value = res.data.access_token
      adminTokenStorage.setTokens(res.data.access_token, refreshToken.value)
    } catch {
      // 刷新失败 → 登出
      logout()
    }
  }

  /**
   * 登出动作
   * 清空内存状态并移除 localStorage 中的令牌，调用后需由调用方跳转到登录页
   */
  function logout() {
    // 清空访问令牌
    token.value = ''
    // 清空刷新令牌
    refreshToken.value = ''
    // 清空用户信息
    user.value = null
    // 统一清除 TokenStorage
    adminTokenStorage.clear()
    localStorage.removeItem('permissions')
  }

  // 导出 Store 的公开状态与动作，供组件与其他 Store 使用
  return { token, refreshToken, user, isLoggedIn, login, logout, fetchMe, doRefresh }
})
