/**
 * 认证（登录 / 注册）API 模块
 *
 * 文件作用：封装商城系统中与"用户认证"相关的后端接口调用，
 *      包括用户登录、用户注册以及获取当前登录用户信息。
 * 所属模块：前端 shop 商城项目的 API 请求层（src/api）。
 * 对外导出内容：
 *  - login：用户登录，换取访问令牌（access_token）
 *  - register：用户注册，创建新账号
 *  - getProfile：获取当前登录用户的个人信息
 *
 * 说明：本模块基于 src/api/index.ts 的 axios 实例发起请求，
 *      登录/注册返回的 token 由 src/stores/auth.ts 负责保存与持久化。
 */
import api from './index'

/**
 * 用户登录
 *
 * 作用：将用户名与密码提交到后端进行身份校验，
 *      校验通过后返回访问令牌（access_token）与用户基本信息。
 * 参数：
 *  - data: { username: string; password: string } 登录表单数据，其中：
 *      - username: string 用户名
 *      - password: string 登录密码（明文提交，依赖 HTTPS 传输加密）
 * 返回值：Axios Promise，响应体 data.data 中携带 access_token 与用户信息
 * 依赖接口：POST /auth/login
 */
export function login(data: { username: string; password: string }) {
  // 将登录表单数据以 JSON 请求体 POST 到 /auth/login 完成身份校验
  return api.post('/auth/login', data)
}

/**
 * 用户注册
 *
 * 作用：将用户填写的注册信息提交到后端创建新账号；
 *      部分后端实现会直接签发 token，实现"注册即登录"。
 * 参数：
 *  - data: {
 *      username: string     用户名（必填）
 *      password: string     密码（必填）
 *      nickname?: string    昵称（可选，用于页面展示）
 *      phone?: string       手机号（可选）
 *      email?: string       邮箱（可选）
 *    }
 * 返回值：Axios Promise，响应体 data.data 中携带 access_token 与用户信息
 * 依赖接口：POST /auth/register
 */
export function register(data: {
  username: string
  password: string
  nickname?: string
  phone?: string
  email?: string
}) {
  // 将注册信息 POST 到 /auth/register，由后端完成账号创建与校验
  return api.post('/auth/register', data)
}

/**
 * 获取当前登录用户信息
 *
 * 作用：依据请求头中自动携带的 token 获取当前登录用户的个人资料，
 *      用于个人中心展示，或登录/注册成功后刷新本地的用户状态。
 * 参数：无
 * 返回值：Axios Promise，响应体 data 中携带用户资料对象
 * 依赖接口：GET /auth/me
 */
export function getProfile() {
  // 调用 /auth/me 接口，token 由 axios 请求拦截器自动附加到请求头
  return api.get('/auth/me')
}
