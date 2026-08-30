/**
 * 用户认证状态管理 Store（Pinia）
 *
 * 文件作用：集中管理当前登录用户的"登录令牌（token）"与"用户信息"等
 *      全局共享状态，并封装登录、注册、拉取用户信息与退出登录等动作。
 * 所属模块：前端 shop 商城项目的全局状态层（src/stores）。
 * 对外导出内容：
 *  - useAuthStore：认证 Store 的工厂函数（组件中调用后获得 store 实例），
 *    实例对外暴露：
 *      - 状态：token（登录令牌）、user（当前用户信息）
 *      - 方法：isLoggedIn、login、register、fetchProfile、logout
 *
 * 说明：token 同步持久化到 localStorage（key 为 shop_token），
 *      因此页面刷新后仍能恢复登录状态。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, register as apiRegister, getProfile } from '@/api/auth'

// 定义并导出认证 Store（采用 setup 风格的定义方式）
export const useAuthStore = defineStore('shop-auth', () => {
  // 登录令牌：初始化时从 localStorage 恢复，实现刷新页面后保持登录态
  const token = ref(localStorage.getItem('shop_token') || '')
  // 当前登录用户信息（结构由后端返回决定，故类型用 any）
  const user = ref<any>(null)

  // 判断当前是否已登录：token 非空即视为已登录
  const isLoggedIn = () => !!token.value

  /**
   * 用户登录
   *
   * 作用：调用登录接口换取访问令牌，成功后保存令牌并拉取用户资料，
   *      使页面整体进入已登录状态。
   * 参数：
   *  - data: { username: string; password: string } 登录表单数据
   * 返回值：无（Promise<void>）；登录失败（未获取到 token）时抛出 Error
   * 依赖接口：POST /auth/login（经 src/api/auth.ts 的 login 封装）
   */
  async function login(data: { username: string; password: string }) {
    // 调用登录接口，等待后端返回访问令牌
    const res = await apiLogin(data)
    // 从响应中取出后端签发的访问令牌（可能嵌套在 data.data 中）
    const t = res.data.data?.access_token
    // 后端未返回 token 视为登录失败，抛出异常由调用方提示
    if (!t) throw new Error('登录失败：未获取到token')
    // 将 token 写入内存状态，供请求拦截器与页面判断登录态使用
    token.value = t
    // 将 token 持久化到 localStorage，刷新页面后不丢失登录态
    localStorage.setItem('shop_token', t)
    // 登录成功后拉取用户资料，同步刷新 user 状态
    await fetchProfile()
  }

  /**
   * 用户注册
   *
   * 作用：调用注册接口创建账号；后端若直接签发 token 则实现"注册即登录"，
   *      随后同样保存令牌并拉取用户资料。
   * 参数：
   *  - data: {
   *      username: string  用户名（必填）
   *      password: string  密码（必填）
   *      nickname?: string 昵称（可选）
   *      email?: string    邮箱（可选）
   *    }
   * 返回值：无（Promise<void>）；注册失败（未获取到 token）时抛出 Error
   * 依赖接口：POST /auth/register（经 src/api/auth.ts 的 register 封装）
   */
  async function register(data: {
    username: string
    password: string
    nickname?: string
    email?: string
  }) {
    // 调用注册接口，等待后端创建账号并返回令牌
    const res = await apiRegister(data)
    // 从响应中取出访问令牌
    const t = res.data.data?.access_token
    // 未获取到 token 视为注册失败
    if (!t) throw new Error('注册失败：未获取到token')
    // 保存令牌到内存状态
    token.value = t
    // 持久化令牌到 localStorage
    localStorage.setItem('shop_token', t)
    // 注册后拉取用户资料，刷新用户状态
    await fetchProfile()
  }

  /**
   * 拉取当前登录用户信息
   *
   * 作用：根据内存中的 token 调用个人信息接口刷新 user 状态；
   *      未登录时直接跳过。获取失败时仅清空 user，不强制登出。
   * 参数：无
   * 返回值：无（Promise<void>）
   * 依赖接口：GET /auth/me（经 src/api/auth.ts 的 getProfile 封装）
   */
  async function fetchProfile() {
    // 未持有 token 时无需请求，直接返回
    if (!token.value) return
    try {
      // 请求后端获取当前用户信息
      const res = await getProfile()
      // 兼容后端两种返回结构：优先取 data.data，否则取整个 data
      user.value = res.data.data ?? res.data
    } catch {
      // 获取用户信息失败时不登出（保留 token），仅将 user 置空
      user.value = null
    }
  }

  /**
   * 退出登录
   *
   * 作用：清空内存中的令牌与用户信息，并移除 localStorage 中持久化的令牌，
   *      使前端整体恢复未登录状态。
   * 参数：无
   * 返回值：无
   */
  function logout() {
    // 清空内存中的令牌状态
    token.value = ''
    // 清空内存中的用户信息
    user.value = null
    // 移除 localStorage 中的令牌，保证刷新后不再恢复登录态
    localStorage.removeItem('shop_token')
  }

  // 对外暴露状态与动作，供组件通过 store 实例调用
  return { token, user, isLoggedIn, login, register, fetchProfile, logout }
})
